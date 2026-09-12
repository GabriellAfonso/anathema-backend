"""A carta em payload: o que o cliente precisa para desenhar, e para mirar.

O contrato está em
`specs/011-deck-catalog-api/contracts/http_catalog.md`.
"""

from apps.game.card_payload import card_payload, catalog_payload
from apps.game.cards import CardType, EffectDuration, TargetKind, mvp_catalog
from apps.game.tests.fake_card_catalog import (
    SAMPLE_SPELL,
    SAMPLE_UNIT,
    FakeCardCatalog,
)

COMMON_FIELDS = {"card_id", "card_type", "name", "energy", "image"}


def test_a_unit_carries_everything_needed_to_draw_it() -> None:
    payload = card_payload(SAMPLE_UNIT)

    assert payload == {
        "card_id": 1,
        "card_type": "unit",
        "name": "SAMPLE UNIT",
        "energy": 2,
        "image": "sample_unit_card",
        "attack": 3,
        "health": 4,
    }


def test_a_spell_carries_the_description_the_player_reads() -> None:
    payload = card_payload(SAMPLE_SPELL)

    assert payload["description"] == "Causa 1 de dano à unidade inimiga alvo."


def test_a_unit_has_no_description_and_no_effect() -> None:
    """Descrição e forma do efeito são de feitiço. Unidade não tem nenhuma das
    duas, e um cliente que as procure numa unidade está com bug."""
    payload = card_payload(SAMPLE_UNIT)

    assert set(payload) == COMMON_FIELDS | {"attack", "health"}


def test_a_spell_has_no_attack_and_no_health() -> None:
    payload = card_payload(SAMPLE_SPELL)

    assert set(payload) == COMMON_FIELDS | {"description", "effect"}


def test_no_card_carries_a_bare_id() -> None:
    """Princípio II da constituição: o espaço de identidade é nomeado."""
    for payload in catalog_payload(mvp_catalog()):
        assert "id" not in payload
        assert "type" not in payload
        assert isinstance(payload["card_id"], int)


def test_the_whole_mvp_comes_out_ordered_by_card_id() -> None:
    payloads = catalog_payload(mvp_catalog())

    card_ids = [int(str(payload["card_id"])) for payload in payloads]

    assert len(payloads) == 29
    assert card_ids == sorted(card_ids)


def test_every_unit_of_the_mvp_carries_attack_and_health() -> None:
    units = [
        payload
        for payload in catalog_payload(mvp_catalog())
        if payload["card_type"] == CardType.UNIT.value
    ]

    assert len(units) == 24
    assert all({"attack", "health"} <= set(unit) for unit in units)


def test_the_payload_of_a_small_catalog_has_only_its_cards() -> None:
    """O catálogo entra por parâmetro: nada aqui alcança o do MVP sozinho."""
    payloads = catalog_payload(FakeCardCatalog([SAMPLE_UNIT]))

    assert [payload["card_id"] for payload in payloads] == [1]


# --- A forma estruturada do efeito (US2) ------------------------------------


def spell_payloads() -> list[dict[str, object]]:
    return [
        payload
        for payload in catalog_payload(mvp_catalog())
        if payload["card_type"] == CardType.SPELL.value
    ]


def effect_of(payload: dict[str, object]) -> dict[str, object]:
    effect = payload["effect"]
    assert isinstance(effect, dict)

    return effect


def test_every_spell_of_the_mvp_carries_the_four_effect_fields() -> None:
    spells = spell_payloads()

    assert len(spells) == 5
    for spell in spells:
        assert set(effect_of(spell)) == {
            "requires_target",
            "target_kind",
            "duration",
            "declaration_only",
        }


def test_requires_target_agrees_with_target_kind() -> None:
    """Não são dois campos independentes: um feitiço com `requires_target`
    verdadeiro e `target_kind` nenhum não é estado nenhum."""
    for spell in spell_payloads():
        effect = effect_of(spell)

        assert effect["requires_target"] is (
            effect["target_kind"] != TargetKind.NONE.value
        )


def test_the_served_values_are_the_ones_the_engine_uses() -> None:
    """O cliente compara esse texto; ele não pode ser uma segunda grafia."""
    target_kinds = {kind.value for kind in TargetKind}
    durations = {duration.value for duration in EffectDuration}

    for spell in spell_payloads():
        effect = effect_of(spell)

        assert effect["target_kind"] in target_kinds
        assert effect["duration"] in durations


def test_the_effect_fields_come_from_the_catalog_card() -> None:
    """Campo a campo contra o molde: a forma servida é a que o motor lê."""
    for spell in mvp_catalog().spells():
        effect = effect_of(card_payload(spell))

        assert effect["requires_target"] == spell.effect.requires_target
        assert effect["target_kind"] == spell.effect.target_kind.value
        assert effect["duration"] == spell.effect.duration.value
        assert effect["declaration_only"] == spell.effect.declaration_only


def test_the_amount_of_an_effect_is_not_served() -> None:
    """Fica de fora de propósito: nem todo efeito tem um, e expô-lo obrigaria
    a um `match` por efeito que duplicaria a união do motor (research D6)."""
    for spell in spell_payloads():
        assert "amount" not in effect_of(spell)
