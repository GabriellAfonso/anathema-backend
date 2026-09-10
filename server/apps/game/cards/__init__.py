"""Catálogo de cartas: a fonte única de verdade sobre quais cartas existem.

Somente leitura em tempo de execução. Nada em partida altera uma carta daqui —
quando uma unidade em campo ganha buff, quem muda é a instância dela, não o
molde.

>>> from apps.game.cards import mvp_catalog
>>> catalog = mvp_catalog()
>>> catalog.card(CardId(1)).name
'JOHN COPPER'

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`: sem esta lista, nenhum consumidor importa daqui.
"""

from .card import (
    SPELL_ID_MIN,
    UNIT_ID_MAX,
    UNIT_ID_MIN,
    Card,
    CardId,
    CardType,
    Spell,
    Unit,
)
from .catalog import (
    CardCatalog,
    CardCatalogError,
    CardIdOutOfRangeError,
    DuplicateCardIdError,
    FrozenCardCatalog,
    UnknownCardError,
)
from .deck_rules import (
    DECK_SIZE,
    MAX_COPIES_PER_CARD,
    Deck,
    DeckProblem,
    InvalidDeckError,
    TooManyCopies,
    UnknownDeckCard,
    WrongDeckSize,
    deck_problems,
    ensure_valid_deck,
)
from .effects import (
    BuffUnitHealth,
    DamageUnit,
    EffectDuration,
    PreventUnitDamage,
    RestoreNexus,
    SacrificeNexusForAttack,
    SpellEffect,
    TargetKind,
)
from .mvp_catalog import MVP_CARDS, MVP_SPELLS, MVP_UNITS, mvp_catalog
from .starter_deck import starter_deck

__all__ = [
    # Cartas
    "Card",
    "CardId",
    "CardType",
    "Spell",
    "Unit",
    "UNIT_ID_MIN",
    "UNIT_ID_MAX",
    "SPELL_ID_MIN",
    # Efeitos
    "SpellEffect",
    "TargetKind",
    "EffectDuration",
    "BuffUnitHealth",
    "PreventUnitDamage",
    "DamageUnit",
    "RestoreNexus",
    "SacrificeNexusForAttack",
    # Catálogo
    "CardCatalog",
    "FrozenCardCatalog",
    "CardCatalogError",
    "UnknownCardError",
    "DuplicateCardIdError",
    "CardIdOutOfRangeError",
    # Cartas do MVP
    "mvp_catalog",
    "MVP_CARDS",
    "MVP_UNITS",
    "MVP_SPELLS",
    # Deck
    "Deck",
    "DeckProblem",
    "WrongDeckSize",
    "TooManyCopies",
    "UnknownDeckCard",
    "InvalidDeckError",
    "deck_problems",
    "ensure_valid_deck",
    "DECK_SIZE",
    "MAX_COPIES_PER_CARD",
    "starter_deck",
]
