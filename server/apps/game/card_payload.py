"""A carta do catálogo na forma que o cliente lê.

O cliente recebe `card_id` em toda mensagem de partida e não tem de onde tirar
nome, custo, ataque, vida nem imagem. Daqui ele tira.

Para feitiço, além da `description` que o jogador lê, sai a **forma
estruturada do efeito**: os quatro campos pelos quais o motor decide a mira. O
cliente decide pelos mesmos campos, e por isso não manda jogada que o servidor
vai recusar. Decisão de regra tomada lendo a descrição em português é bug, aqui
como no motor.

O contrato está em `specs/011-deck-catalog-api/contracts/http_catalog.md`.
"""

from apps.game.cards import Card, CardCatalog, Spell, SpellEffect, Unit

CardPayload = dict[str, object]
EffectPayload = dict[str, object]


def catalog_payload(catalog: CardCatalog) -> list[CardPayload]:
    """Todas as cartas, ordenadas por `card_id`, como o catálogo as entrega.

    O catálogo entra por parâmetro: nada aqui alcança o do MVP sozinho.

    >>> len(catalog_payload(mvp_catalog()))
    29
    """
    return [card_payload(card) for card in catalog.all_cards()]


def card_payload(card: Card) -> CardPayload:
    """Uma carta, com os campos do tipo dela e nenhum do outro tipo.

    >>> card_payload(mvp_catalog().card(CardId(1)))["card_type"]
    'unit'
    """
    if isinstance(card, Unit):
        return _unit_payload(card)

    return _spell_payload(card)


def _unit_payload(unit: Unit) -> CardPayload:
    """Unidade: os campos comuns, mais ataque e vida."""
    return {
        **_common_payload(unit),
        "attack": unit.attack,
        "health": unit.health,
    }


def _spell_payload(spell: Spell) -> CardPayload:
    """Feitiço: os campos comuns, a descrição do jogador e a forma do efeito."""
    return {
        **_common_payload(spell),
        "description": spell.description,
        "effect": _effect_payload(spell.effect),
    }


def _common_payload(card: Card) -> CardPayload:
    """`card_id` e `card_type`, nunca `id` e `type` (constituição, II)."""
    return {
        "card_id": int(card.card_id),
        "card_type": card.card_type.value,
        "name": card.name,
        "energy": card.energy,
        "image": card.image,
    }


def _effect_payload(effect: SpellEffect) -> EffectPayload:
    """Os quatro campos que todo efeito declara ao motor.

    Lidos da base comum `SpellEffectShape`, sem `match` sobre a união: um
    efeito novo é servido certo sem tocar neste módulo. `amount` fica de fora
    de propósito -- nem todo efeito tem um, e expô-lo exigiria justamente o
    `match` que isto evita.

    >>> _effect_payload(DamageUnit(amount=3))["target_kind"]
    'enemy_unit'
    """
    return {
        "requires_target": effect.requires_target,
        "target_kind": effect.target_kind.value,
        "duration": effect.duration.value,
        "declaration_only": effect.declaration_only,
    }
