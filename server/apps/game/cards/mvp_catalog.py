"""As 29 cartas do MVP: 24 unidades e 5 feitiços.

Os valores vêm do jogo anterior (`dumcrown/server/cards_data`) e são
reaproveitados como estão — esta feature mudou o formato, não o balanceamento.
O campo que lá se chamava `defense` é a vida da unidade e aqui se chama
`health`.

Os `card_id` das unidades são os herdados; os feitiços perderam o prefixo `s` e
receberam 1001 a 1005, na ordem original.
"""

from .card import Card, CardId, Spell, Unit
from .catalog import CardCatalog, FrozenCardCatalog
from .effects import (
    BuffUnitHealth,
    DamageUnit,
    PreventUnitDamage,
    RestoreNexus,
    SacrificeNexusForAttack,
    SpellEffect,
)


def _unit(
    card_id: int,
    name: str,
    *,
    energy: int,
    attack: int,
    health: int,
    image: str,
) -> Unit:
    """Embrulha o `int` em `CardId` para o resto do arquivo ficar legível."""
    return Unit(
        card_id=CardId(card_id),
        name=name,
        energy=energy,
        attack=attack,
        health=health,
        image=image,
    )


def _spell(
    card_id: int,
    name: str,
    *,
    energy: int,
    description: str,
    effect: SpellEffect,
    image: str,
) -> Spell:
    """Mesma razão de `_unit`."""
    return Spell(
        card_id=CardId(card_id),
        name=name,
        energy=energy,
        description=description,
        effect=effect,
        image=image,
    )


MVP_UNITS: tuple[Unit, ...] = (
    _unit(1, "JOHN COPPER", energy=5, attack=7, health=5, image="john_card"),
    _unit(2, "CAROL ARLET", energy=5, attack=7, health=6, image="carol_card"),
    _unit(3, "MORTEM", energy=5, attack=7, health=2, image="mortem_card"),
    _unit(4, "KRONOS", energy=6, attack=7, health=4, image="kronos_card"),
    _unit(5, "DARK AGE", energy=1, attack=3, health=2, image="darkage1_card"),
    _unit(6, "KHRAS", energy=1, attack=2, health=4, image="khras_card"),
    _unit(7, "SKILLET", energy=2, attack=4, health=5, image="skillet_card"),
    _unit(8, "CDC", energy=4, attack=6, health=2, image="cdc_card"),
    _unit(9, "OKADA", energy=6, attack=8, health=5, image="okada_card"),
    _unit(
        10, "SMOOTH CRIMINAL", energy=3, attack=4, health=3, image="smoothcriminal_card"
    ),
    _unit(11, "BOOGIE", energy=2, attack=4, health=1, image="boogie_card"),
    _unit(12, "SPRING", energy=4, attack=7, health=1, image="spring_card"),
    _unit(13, "POLAROID", energy=3, attack=2, health=6, image="polaroid_card"),
    _unit(14, "MANIAC", energy=7, attack=10, health=1, image="maniac_card"),
    _unit(15, "CRAZY", energy=1, attack=2, health=4, image="crazy_card"),
    _unit(16, "THE O'JAYS", energy=8, attack=10, health=5, image="theojays_card"),
    _unit(17, "NEON B.", energy=8, attack=3, health=10, image="neonb_card"),
    _unit(18, "BALLHAN", energy=1, attack=1, health=4, image="ballhan_card"),
    _unit(
        19, "DARK NECESSITES", energy=2, attack=5, health=1, image="darknecessites_card"
    ),
    _unit(20, "ANOMALY", energy=8, attack=8, health=8, image="anomaly_card"),
    _unit(
        21, "RHIOROS GHOST", energy=1, attack=1, health=1, image="rhioros_ghost_card"
    ),
    _unit(55, "DARK AGE II", energy=4, attack=5, health=3, image="darkage2_card"),
    _unit(56, "DARK AGE III", energy=8, attack=7, health=5, image="darkage3_card"),
    _unit(57, "DARK AGE IV", energy=10, attack=9, health=10, image="darkage4_card"),
)


# As descrições foram reescritas para o vocabulário novo: a vida da unidade é
# "vida", a vida do jogador é "Nexus", e "defesa" não aparece — no jogo anterior
# ela dizia "aumenta +2 de defesa", que hoje confundiria com bloqueio.
MVP_SPELLS: tuple[Spell, ...] = (
    _spell(
        1001,
        "SOMEONE'S SHIELD",
        energy=2,
        description="Soma 2 de vida à unidade aliada alvo.",
        effect=BuffUnitHealth(amount=2),
        image="someones_shield",
    ),
    _spell(
        1002,
        "MAGIC BARRIER",
        energy=3,
        description="A unidade aliada alvo ignora o próximo dano que receber.",
        effect=PreventUnitDamage(),
        image="magic_barrier",
    ),
    _spell(
        1003,
        "SACRIFICIAL FIRE",
        energy=8,
        description=(
            "Só na declaração de ataque. Você perde 8 de Nexus, sem cair abaixo "
            "de 1, e a unidade aliada alvo na zona de ataque ganha 3 de ataque."
        ),
        effect=SacrificeNexusForAttack(nexus_cost=8, attack_bonus=3),
        image="sacrificial_fire",
    ),
    _spell(
        1004,
        "LIFE POTION",
        energy=4,
        description="Você recupera 5 de Nexus.",
        effect=RestoreNexus(amount=5),
        image="life_potion",
    ),
    _spell(
        1005,
        "SUMMONED AX",
        energy=5,
        description="Causa 3 de dano à unidade inimiga alvo.",
        effect=DamageUnit(amount=3),
        image="summoned_ax",
    ),
)


MVP_CARDS: tuple[Card, ...] = MVP_UNITS + MVP_SPELLS


def mvp_catalog() -> CardCatalog:
    """O catálogo do MVP, validado na chamada.

    Só o ponto de composição da aplicação chama isto; o resto do código recebe
    um `CardCatalog` por parâmetro.

    >>> mvp_catalog().card(CardId(1)).name
    'JOHN COPPER'
    """
    return FrozenCardCatalog(MVP_CARDS)
