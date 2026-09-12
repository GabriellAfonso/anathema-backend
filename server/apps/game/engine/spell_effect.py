"""Executa os cinco efeitos do MVP sobre a partida.

**Este módulo não sabe de que fase a chamada veio, e não existe parâmetro que
diga.** Quem chama é `cast_spell`, na Fase de Ação e na janela do defensor
(§5B, §7.2), com o alvo que a guarda de lançamento acabou de validar. É o mesmo
efeito com o mesmo resultado nas duas fases.

Um parâmetro de origem -- mesmo um booleano -- convidaria o primeiro `if` que
faz as duas fases divergirem, e a partir daí existiriam duas implementações de
cada efeito para manter iguais à mão.

O despacho é um `match` exaustivo sobre `SpellEffect`, a união fechada que
`cards/effects.py` escreveu prevendo este módulo: um efeito novo sem braço é
erro de mypy, não comportamento ausente em produção.

A duração de todo modificador criado vem de `effect.duration`, **nunca de um
literal**. É o que faz o Fim de Rodada varrer a imunidade e não varrer o buff de
vida sem que este módulo saiba o que é varrido -- a §8 continua sendo a única
dona dessa regra.
"""

from typing import assert_never

from apps.game.cards import (
    BuffUnitHealth,
    CardCatalog,
    DamageUnit,
    PreventUnitDamage,
    RestoreNexus,
    SacrificeNexusForAttack,
    SpellEffect,
)
from apps.game.match import (
    AttackModifier,
    BankUnit,
    DamageImmunity,
    HealthModifier,
    Match,
    PlayerState,
)

from .unit_damage import bury_dead_units, deal_damage_to_unit
from .unit_vitals import unit_has_damage_immunity
from .victory import change_nexus

# Fluxo de Partida §14: o SACRIFICIAL FIRE nunca deixa o Nexus abaixo disto.
MIN_NEXUS_AFTER_SACRIFICE = 1


class SpellEffectNeedsTargetError(Exception):
    """Um efeito que exige alvo chegou aqui sem alvo.

    Estado corrompido, não jogada: a §5B valida o alvo no lançamento, na mesma
    jogada que chama isto. Recusa nomeada em vez de `assert` -- que some com
    `-O` -- pela mesma razão de `round_end._swap_token`.

    >>> raise SpellEffectNeedsTargetError(DamageUnit(amount=3))
    SpellEffectNeedsTargetError: effect DamageUnit(amount=3) needs an
    'enemy_unit': got no target
    """

    def __init__(self, effect: SpellEffect) -> None:
        super().__init__(
            f"effect {effect!r} needs an '{effect.target_kind}': got no target"
        )
        self.effect = effect


def apply_spell_effect(
    match: Match,
    caster: PlayerState,
    effect: SpellEffect,
    target: BankUnit | None,
    *,
    catalog: CardCatalog,
) -> None:
    """Aplica um dos cinco efeitos, e apura o que o efeito deixou para trás.

    `target` já vem validado. `None` significa que o efeito **não mira nada** --
    a guarda de lançamento recusa alvo fora de campo antes de chegar aqui.

    A morte é verificada assim que o efeito termina: o feitiço seguinte da
    mesma vez precisa enxergar o alvo já morto, e é isso que faz um SUMMONED AX
    seguido de outro recusar o segundo por alvo fora de campo. A vitória (§10) é
    apurada dentro de `change_nexus`, junto do evento que alterou o Nexus.

    >>> apply_spell_effect(match, caster, DamageUnit(amount=3), unit,
    ...                    catalog=catalog)
    >>> unit.damage_taken
    3
    """
    _dispatch(match, caster, effect, target)

    bury_dead_units(match, catalog=catalog)


def _dispatch(
    match: Match, caster: PlayerState, effect: SpellEffect, target: BankUnit | None
) -> None:
    """Um braço por efeito.

    O `assert_never` é o que torna a exaustividade **verificada**: um `match`
    que devolve `None` não obriga o mypy a cobrir a união sozinho, ao contrário
    de `to_modifier_document`, que devolve valor e por isso já é checado. Sem
    ele, um efeito novo sem braço passaria batido e sumiria em produção.
    """
    match effect:
        case BuffUnitHealth():
            _buff_unit_health(_targeted(effect, target), effect)
        case PreventUnitDamage():
            _prevent_unit_damage(_targeted(effect, target), effect)
        case DamageUnit():
            deal_damage_to_unit(_targeted(effect, target), effect.amount)
        case RestoreNexus():
            change_nexus(match, caster, effect.amount)
        case SacrificeNexusForAttack():
            _sacrifice_nexus_for_attack(match, caster, effect)
        case _:
            assert_never(effect)


def _buff_unit_health(target: BankUnit, effect: BuffUnitHealth) -> None:
    """SOMEONE'S SHIELD: soma vida à unidade aliada alvo.

    Somar vida **não é curar**: `damage_taken` não é tocado, e uma unidade
    danificada só fica com mais vida restante.
    """
    target.modifiers.append(
        HealthModifier(amount=effect.amount, duration=effect.duration)
    )


def _prevent_unit_damage(target: BankUnit, effect: PreventUnitDamage) -> None:
    """MAGIC BARRIER: a unidade aliada alvo ignora o próximo dano (§14).

    Não acumula: uma unidade que já tem barreira fica como está. A duração vem
    do efeito -- permanente desde a correção da nota de 2026-09-11 --, e quem a
    tira é o dano que ela absorve, não o Fim de Rodada.
    """
    if unit_has_damage_immunity(target):
        return

    target.modifiers.append(DamageImmunity(duration=effect.duration))


def _sacrifice_nexus_for_attack(
    match: Match, caster: PlayerState, effect: SacrificeNexusForAttack
) -> None:
    """SACRIFICIAL FIRE (§14): a zona de ataque inteira ganha ataque, e o
    lançador paga.

    Sem alvo. A zona é lida **neste instante**, e é só isso que faz uma unidade
    mandada depois não ganhar nada -- não existe marca a guardar. Entre as
    features 009 e 010 este braço pedia um alvo e buffava uma unidade só.

    O buff vem **antes** do custo, e a troca é indivisível: o custo não existe
    sem o buff. O custo nunca deixa o Nexus abaixo de 1 -- com Nexus 1, joga
    sem perder nada --, e por isso o FIRE não derrota ninguém (§10).
    """
    for unit in _attacking_units(match):
        unit.modifiers.append(
            AttackModifier(amount=effect.attack_bonus, duration=effect.duration)
        )

    change_nexus(match, caster, -_affordable_nexus_cost(caster, effect))


def _attacking_units(match: Match) -> list[BankUnit]:
    """As unidades que estão na zona de ataque agora (§7.1).

    `ongoing_combat` não é leitura de fase disfarçada: a guarda de momento da
    §14 já exigiu a Declaração antes de o efeito ser alcançado, então o combate
    existe. Unidade que saiu de campo entre a declaração e o lançamento é
    ignorada, pela mesma razão do bloqueador órfão da §7.3.
    """
    return [
        unit
        for card_instance_id in match.ongoing_combat().attacker_card_instance_ids
        if (unit := match.bank_unit(card_instance_id)) is not None
    ]


def _affordable_nexus_cost(caster: PlayerState, effect: SacrificeNexusForAttack) -> int:
    """Quanto o FIRE cobra de verdade: `nexus = max(nexus - custo, 1)` (§14).

    >>> _affordable_nexus_cost(caster_with_nexus_5, SacrificeNexusForAttack(8, 3))
    4
    """
    return max(min(effect.nexus_cost, caster.nexus - MIN_NEXUS_AFTER_SACRIFICE), 0)


def _targeted(effect: SpellEffect, target: BankUnit | None) -> BankUnit:
    """O alvo de um efeito que exige alvo, ou recusa citando o efeito."""
    if target is None:
        raise SpellEffectNeedsTargetError(effect)

    return target
