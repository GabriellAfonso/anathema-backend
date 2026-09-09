"""Conferência das 29 cartas contra os dados do jogo anterior.

A tabela abaixo é a transcrição de `dumcrown/server/cards_data/units.py` e
`spells.py`, com `defense` lido como vida da unidade. Se um valor divergir aqui,
o catálogo mudou o balanceamento — que esta feature não tinha licença para
mexer.
"""

from apps.game.cards.card import (
    SPELL_ID_MIN,
    UNIT_ID_MAX,
    UNIT_ID_MIN,
    CardId,
    Spell,
    Unit,
)
from apps.game.cards.mvp_catalog import MVP_SPELLS, MVP_UNITS, mvp_catalog

# card_id, nome, energia, ataque, vida, imagem
EXPECTED_UNITS: tuple[tuple[int, str, int, int, int, str], ...] = (
    (1, "JOHN COPPER", 5, 7, 5, "john_card"),
    (2, "CAROL ARLET", 5, 7, 6, "carol_card"),
    (3, "MORTEM", 5, 7, 2, "mortem_card"),
    (4, "KRONOS", 6, 7, 4, "kronos_card"),
    (5, "DARK AGE", 1, 3, 2, "darkage1_card"),
    (6, "KHRAS", 1, 2, 4, "khras_card"),
    (7, "SKILLET", 2, 4, 5, "skillet_card"),
    (8, "CDC", 4, 6, 2, "cdc_card"),
    (9, "OKADA", 6, 8, 5, "okada_card"),
    (10, "SMOOTH CRIMINAL", 3, 4, 3, "smoothcriminal_card"),
    (11, "BOOGIE", 2, 4, 1, "boogie_card"),
    (12, "SPRING", 4, 7, 1, "spring_card"),
    (13, "POLAROID", 3, 2, 6, "polaroid_card"),
    (14, "MANIAC", 7, 10, 1, "maniac_card"),
    (15, "CRAZY", 1, 2, 4, "crazy_card"),
    (16, "THE O'JAYS", 8, 10, 5, "theojays_card"),
    (17, "NEON B.", 8, 3, 10, "neonb_card"),
    (18, "BALLHAN", 1, 1, 4, "ballhan_card"),
    (19, "DARK NECESSITES", 2, 5, 1, "darknecessites_card"),
    (20, "ANOMALY", 8, 8, 8, "anomaly_card"),
    (21, "RHIOROS GHOST", 1, 1, 1, "rhioros_ghost_card"),
    (55, "DARK AGE II", 4, 5, 3, "darkage2_card"),
    (56, "DARK AGE III", 8, 7, 5, "darkage3_card"),
    (57, "DARK AGE IV", 10, 9, 10, "darkage4_card"),
)

# card_id, nome, energia, imagem — o efeito é conferido em test_spell_effects.py
EXPECTED_SPELLS: tuple[tuple[int, str, int, str], ...] = (
    (1001, "SOMEONE'S SHIELD", 2, "someones_shield"),
    (1002, "MAGIC BARRIER", 3, "magic_barrier"),
    (1003, "SACRIFICIAL FIRE", 8, "sacrificial_fire"),
    (1004, "LIFE POTION", 4, "life_potion"),
    (1005, "SUMMONED AX", 5, "summoned_ax"),
)


def test_the_catalog_has_the_twenty_nine_mvp_cards() -> None:
    assert len(MVP_UNITS) == 24
    assert len(MVP_SPELLS) == 5


def test_every_unit_matches_the_source_data() -> None:
    catalog = mvp_catalog()

    for card_id, name, energy, attack, health, image in EXPECTED_UNITS:
        unit = catalog.card(CardId(card_id))

        assert isinstance(unit, Unit)
        assert (unit.name, unit.energy, unit.attack, unit.health, unit.image) == (
            name,
            energy,
            attack,
            health,
            image,
        )


def test_every_spell_matches_the_source_data() -> None:
    catalog = mvp_catalog()

    for card_id, name, energy, image in EXPECTED_SPELLS:
        spell = catalog.card(CardId(card_id))

        assert isinstance(spell, Spell)
        assert (spell.name, spell.energy, spell.image) == (name, energy, image)


def test_no_spell_description_says_defesa() -> None:
    """ "Defesa" colide com bloqueio; o vocabulário novo diz vida e Nexus."""
    for spell in MVP_SPELLS:
        assert "defesa" not in spell.description.lower()


def test_units_and_spells_sit_in_their_allocated_ranges() -> None:
    for unit in MVP_UNITS:
        assert UNIT_ID_MIN <= unit.card_id <= UNIT_ID_MAX

    for spell in MVP_SPELLS:
        assert spell.card_id >= SPELL_ID_MIN


def test_every_card_id_is_unique() -> None:
    card_ids = [card.card_id for card in MVP_UNITS + MVP_SPELLS]

    assert len(set(card_ids)) == len(card_ids)
