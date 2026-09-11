"""Alterações ativas sobre uma unidade no banco, com a duração que o Fim de
Rodada lê.

Modificador é alteração **com duração**: entra na lista, vale enquanto está
lá, sai e deixa de valer. Dano não é modificador — não expira, não some no Fim
de Rodada, e mora em `BankUnit.damage_taken`.

Aplicar e varrer modificador não é deste pacote. Aqui eles só são
representados.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from apps.game.cards import EffectDuration


class ModifierKind(StrEnum):
    """Discriminante da união, e o que sobrevive à ida e volta pelo JSON.

    Uma união de dataclasses não volta do JSON sozinha: `{"amount": 2}` serve
    tanto para ataque quanto para vida. Este campo é o que decide qual é qual
    na leitura.
    """

    ATTACK = "attack"
    HEALTH = "health"
    DAMAGE_IMMUNITY = "damage_immunity"


@dataclass(frozen=True, slots=True)
class AttackModifier:
    """Soma ao ataque da unidade. `amount` negativo é como se reduz ataque.

    Não existe campo de ataque na instância: o efetivo é o do molde mais a
    soma destes. Fazer essa conta é do motor de regras.

    >>> AttackModifier(amount=2, duration=EffectDuration.PERMANENT).amount
    2
    """

    # `ClassVar` porque a espécie pertence à mecânica, não à instância: assim
    # nenhum call site consegue construir um AttackModifier que se diz `health`.
    modifier_kind: ClassVar[ModifierKind] = ModifierKind.ATTACK

    amount: int
    duration: EffectDuration


@dataclass(frozen=True, slots=True)
class HealthModifier:
    """Soma à vida efetiva da unidade. Não cura: cura abaixa `damage_taken`.

    >>> HealthModifier(amount=2, duration=EffectDuration.PERMANENT).modifier_kind
    <ModifierKind.HEALTH: 'health'>
    """

    modifier_kind: ClassVar[ModifierKind] = ModifierKind.HEALTH

    amount: int
    duration: EffectDuration


@dataclass(frozen=True, slots=True)
class DamageImmunity:
    """A barreira da MAGIC BARRIER: o próximo dano não entra, e ela some.

    Consumir a barreira é regra, e mora em `engine/unit_damage.py`; aqui ela só
    é representada. Até a correção da nota de 2026-09-11 era imunidade até o
    fim da rodada, e o nome ficou.

    Sem `amount`: a mecânica é tudo ou nada. Um campo de quantidade anulável
    deixaria existir `DamageImmunity(amount=5)`, que não é estado nenhum — é o
    mesmo argumento que `effects.py` usa para `requires_target` ser derivado.

    >>> DamageImmunity(duration=EffectDuration.PERMANENT).duration
    <EffectDuration.PERMANENT: 'permanent'>
    """

    modifier_kind: ClassVar[ModifierKind] = ModifierKind.DAMAGE_IMMUNITY

    duration: EffectDuration


# União fechada: um `match` sobre `UnitModifier` que esqueça um braço é erro de
# mypy, não bug em produção. Mesma disciplina de `SpellEffect` em `cards`.
UnitModifier = AttackModifier | HealthModifier | DamageImmunity
