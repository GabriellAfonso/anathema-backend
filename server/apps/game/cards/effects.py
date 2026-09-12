"""O que um feitiço faz, em campos que o motor lê sem interpretar português.

A `description` da carta existe para o cliente mostrar ao jogador. Decisão de
regra que dependa dela é bug: o motor decide por `target_kind`, por `duration`
e pela classe do efeito.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class TargetKind(StrEnum):
    """Que tipo de alvo o feitiço aceita. Conjunto fechado."""

    NONE = "none"
    ALLIED_UNIT = "allied_unit"
    ENEMY_UNIT = "enemy_unit"
    # Houve um quarto, `ALLIED_ATTACKER`, entre as features 009 e 010: unidade
    # aliada na zona de ataque, exigida por uma versão do SACRIFICIAL FIRE que a
    # §14 não descreve. Com o FIRE sem alvo, ele ficou sem nenhum usuário.


class EffectDuration(StrEnum):
    """Por quanto tempo o efeito vale. Conjunto fechado."""

    PERMANENT = "permanent"
    # O Fim de Rodada varre o que estiver marcado assim (Fluxo de Partida §8).
    UNTIL_END_OF_ROUND = "until_end_of_round"


class SpellEffectShape:
    """O que todo efeito declara para o motor decidir antes de aceitar a jogada.

    `target_kind`, `duration` e `declaration_only` são `ClassVar` porque
    pertencem à mecânica, não à instância: assim nenhum call site consegue
    construir SUMMONED AX mirando unidade aliada.

    `declaration_only` é o "momento permitido pelo feitiço" da §5B: a §14 dá a
    um feitiço do MVP -- o SACRIFICIAL FIRE -- a regra de só valer na declaração
    de ataque. Sem default, como as outras duas: um efeito novo que esqueça de
    responder é erro de mypy.
    """

    __slots__ = ()

    target_kind: ClassVar[TargetKind]
    duration: ClassVar[EffectDuration]
    declaration_only: ClassVar[bool]

    @property
    def requires_target(self) -> bool:
        """Se a jogada precisa de alvo para ser aceita.

        Derivado, não campo: campo separado deixaria existir um efeito com
        `requires_target=True` e `target_kind=NONE`, que não é estado nenhum.

        >>> DamageUnit(amount=3).requires_target
        True
        """
        return self.target_kind is not TargetKind.NONE


@dataclass(frozen=True, slots=True)
class BuffUnitHealth(SpellEffectShape):
    """Soma vida a uma unidade aliada, para sempre.

    >>> BuffUnitHealth(amount=2).target_kind
    <TargetKind.ALLIED_UNIT: 'allied_unit'>
    """

    target_kind: ClassVar[TargetKind] = TargetKind.ALLIED_UNIT
    duration: ClassVar[EffectDuration] = EffectDuration.PERMANENT
    declaration_only: ClassVar[bool] = False

    amount: int


@dataclass(frozen=True, slots=True)
class PreventUnitDamage(SpellEffectShape):
    """A unidade aliada alvo ignora o próximo dano que receber (§14).

    De qualquer fonte -- combate ou feitiço --, e a barreira some com ele. Não
    expira no fim da rodada, e não acumula: uma segunda barreira na mesma
    unidade não soma nada. Até a correção da nota de 2026-09-11 ela era
    imunidade total até o fim da rodada.

    Sem campo próprio: a mecânica é tudo ou nada, não tem quantidade.

    >>> PreventUnitDamage().duration
    <EffectDuration.PERMANENT: 'permanent'>
    """

    target_kind: ClassVar[TargetKind] = TargetKind.ALLIED_UNIT
    duration: ClassVar[EffectDuration] = EffectDuration.PERMANENT
    declaration_only: ClassVar[bool] = False


@dataclass(frozen=True, slots=True)
class DamageUnit(SpellEffectShape):
    """Causa dano a uma unidade inimiga.

    >>> DamageUnit(amount=3).target_kind
    <TargetKind.ENEMY_UNIT: 'enemy_unit'>
    """

    target_kind: ClassVar[TargetKind] = TargetKind.ENEMY_UNIT
    duration: ClassVar[EffectDuration] = EffectDuration.PERMANENT
    declaration_only: ClassVar[bool] = False

    amount: int


@dataclass(frozen=True, slots=True)
class RestoreNexus(SpellEffectShape):
    """O próprio jogador recupera Nexus. Sem alvo.

    >>> RestoreNexus(amount=5).target_kind
    <TargetKind.NONE: 'none'>
    """

    target_kind: ClassVar[TargetKind] = TargetKind.NONE
    duration: ClassVar[EffectDuration] = EffectDuration.PERMANENT
    declaration_only: ClassVar[bool] = False

    amount: int


@dataclass(frozen=True, slots=True)
class SacrificeNexusForAttack(SpellEffectShape):
    """O atacante paga Nexus, e a zona de ataque dele inteira ganha ataque.

    Regra própria da §14: **sem alvo**, só na declaração de ataque, só pelo
    atacante; todas as unidades dele que estão na zona naquele instante ganham o
    bônus, e o Nexus nunca cai abaixo de 1.

    Entre as features 009 e 010 o motor exigia alvo e buffava uma unidade só --
    regra que a nota nunca descreveu, corrigida na 010.

    Efeito composto porque a troca é indivisível: o custo em Nexus não existe
    sem o buff, nem o buff sem o custo.

    >>> SacrificeNexusForAttack(nexus_cost=8, attack_bonus=3).target_kind
    <TargetKind.NONE: 'none'>
    """

    target_kind: ClassVar[TargetKind] = TargetKind.NONE
    duration: ClassVar[EffectDuration] = EffectDuration.PERMANENT
    declaration_only: ClassVar[bool] = True

    nexus_cost: int
    attack_bonus: int


# União fechada: o `match` que a executa é `engine/spell_effect.py`, e um braço
# esquecido lá é erro de mypy, não bug em produção. Ele fecha o `match` com
# `assert_never`, que é o que torna a exaustividade verificada num despacho que
# devolve `None`.
SpellEffect = (
    BuffUnitHealth
    | PreventUnitDamage
    | DamageUnit
    | RestoreNexus
    | SacrificeNexusForAttack
)
