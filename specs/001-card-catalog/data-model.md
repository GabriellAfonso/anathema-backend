# Fase 1 — Modelo de dados

**Feature**: Catálogo de Cartas do MVP (`001-card-catalog`)
**Data**: 2026-09-09

Nada aqui vai para banco. "Modelo" quer dizer os tipos em memória que o pacote
`apps.game.cards` define e as invariantes que eles garantem.

---

## Tipos base — `cards/card.py`

### `CardId`

`NewType("CardId", int)`. Identificador de carta, único em todo o catálogo.
Distinto de `user_id` para o mypy, apesar de os dois serem inteiros.

### `CardType`

`StrEnum` fechado.

| Membro | Valor | Significado |
|---|---|---|
| `UNIT` | `"unit"` | Carta permanente, vai para o banco |
| `SPELL` | `"spell"` | Carta de efeito único, vai para o cemitério |

### Faixas de identificador

| Constante | Valor | Regra |
|---|---|---|
| `UNIT_ID_MIN` | 1 | Menor `card_id` de unidade |
| `UNIT_ID_MAX` | 1000 | Maior `card_id` de unidade |
| `SPELL_ID_MIN` | 1001 | Menor `card_id` de feitiço |

Convenção de alocação, verificada na carga (D8). **Não** é como se descobre o
tipo de uma carta — isso é `card_type` (FR-005).

### `Unit`

`@dataclass(frozen=True, slots=True)`

| Campo | Tipo | Origem | Notas |
|---|---|---|---|
| `card_id` | `CardId` | herdado do jogo anterior | 1–21, 55–57 |
| `card_type` | `CardType` | fixo | sempre `CardType.UNIT` |
| `name` | `str` | herdado | inglês, caixa alta |
| `energy` | `int` | herdado | custo para jogar |
| `attack` | `int` | herdado | dano que causa em combate |
| `health` | `int` | herdado, era `defense` | vida da unidade |
| `image` | `str` | herdado | metadado opaco ao motor |

`health`, nunca `defense` (FR-010) e nunca `nexus` (FR-011). "Defesa" colidiria
com bloqueio; `nexus` é a vida do jogador, que nem existe neste pacote.

### `Spell`

`@dataclass(frozen=True, slots=True)`

| Campo | Tipo | Notas |
|---|---|---|
| `card_id` | `CardId` | 1001–1005 |
| `card_type` | `CardType` | sempre `CardType.SPELL` |
| `name` | `str` | inglês, caixa alta |
| `energy` | `int` | custo para jogar |
| `description` | `str` | português, **só para o cliente** — o motor nunca lê |
| `effect` | `SpellEffect` | o que o motor lê |
| `image` | `str` | metadado opaco |

### `Card`

`Card = Unit | Spell`. União fechada: um `match` sobre `Card` que esqueça um
braço é erro de mypy.

---

## Efeitos — `cards/effects.py`

### `TargetKind`

`StrEnum` fechado. Responde "que tipo de alvo o feitiço aceita" (FR-014b).

| Membro | Valor |
|---|---|
| `NONE` | `"none"` |
| `ALLIED_UNIT` | `"allied_unit"` |
| `ENEMY_UNIT` | `"enemy_unit"` |

### `EffectDuration`

`StrEnum` fechado. Responde "por quanto tempo vale" (FR-014c). O segundo valor é
o que a limpeza de Fim de Rodada procura (Fluxo de Partida §8).

| Membro | Valor |
|---|---|
| `PERMANENT` | `"permanent"` |
| `UNTIL_END_OF_ROUND` | `"until_end_of_round"` |

### Efeitos concretos

Todos `@dataclass(frozen=True, slots=True)`, todos com `target_kind` e
`duration`, mais os números da própria mecânica.

| Classe | Campos próprios | `target_kind` | `duration` |
|---|---|---|---|
| `BuffUnitHealth` | `amount: int` | `ALLIED_UNIT` | `PERMANENT` |
| `PreventUnitDamage` | — | `ALLIED_UNIT` | `UNTIL_END_OF_ROUND` |
| `DamageUnit` | `amount: int` | `ENEMY_UNIT` | `PERMANENT` |
| `RestoreNexus` | `amount: int` | `NONE` | `PERMANENT` |
| `SacrificeNexusForAttack` | `nexus_cost: int`, `attack_bonus: int` | `NONE` | `PERMANENT` |

`SpellEffect` é a união dos cinco.

### `requires_target`

Propriedade derivada, não campo: `target_kind is not TargetKind.NONE`. Atende
FR-014a sem abrir a possibilidade de um efeito declarar `requires_target=True`
com `target_kind=NONE` — estado impossível que um campo separado permitiria.

---

## Catálogo — `cards/catalog.py`

### `CardCatalog` (Protocol)

| Método | Retorno | Contrato |
|---|---|---|
| `card(card_id)` | `Card` | Levanta `UnknownCardError` se não existir |
| `all_cards()` | `tuple[Card, ...]` | Todas, em ordem de `card_id` |
| `units()` | `tuple[Unit, ...]` | Filtra por `card_type`, nunca por faixa |
| `spells()` | `tuple[Spell, ...]` | Idem. Lista vazia é resultado válido |

### `FrozenCardCatalog`

Implementação única de produção. Recebe uma sequência de cartas no construtor e
monta o índice por `card_id`. Depois disso, imutável.

**Invariantes verificadas na construção**:

| Invariante | Falha com | Mensagem contém |
|---|---|---|
| Nenhum `card_id` repetido | `DuplicateCardIdError` | o `card_id` em conflito |
| Unidade em 1–1000 | `CardIdOutOfRangeError` | o `card_id`, o tipo e a faixa esperada |
| Feitiço em 1001 ou acima | `CardIdOutOfRangeError` | idem |

### Erros

| Exceção | Quando | Mensagem |
|---|---|---|
| `UnknownCardError` | `card()` com `card_id` inexistente | inclui o `card_id` pedido (FR-018) |
| `DuplicateCardIdError` | carga com id repetido | inclui o `card_id` duplicado (FR-030) |
| `CardIdOutOfRangeError` | carga com id fora da faixa do tipo | inclui id, tipo e faixa |

Todas herdam de um `CardCatalogError` comum, para o chamador que quiser capturar
o conjunto.

---

## Dados do MVP — `cards/mvp_catalog.py`

As 29 cartas do apêndice *Dados de Origem* da spec, construídas por dois
auxiliares (`_unit(...)` e `_spell(...)`) que embrulham o `int` em `CardId` e
fixam o `card_type`. Expõe `mvp_catalog() -> CardCatalog`.

Valores numéricos idênticos ao jogo anterior (FR-002); `defense` lido como
`health`. As descrições dos 5 feitiços são reescritas para o vocabulário novo —
"vida da unidade" e "Nexus", nunca "defesa".

---

## Regras de deck — `cards/deck_rules.py`

### Constantes

| Constante | Valor | Origem |
|---|---|---|
| `DECK_SIZE` | 40 | `Game/Fluxo de Partida.md` §12 |
| `MAX_COPIES_PER_CARD` | 3 | pedido do maintainer, sem nota de decisão ainda |

### `Deck`

`Deck = Sequence[CardId]`. Uma lista, não um conjunto: repetição é esperada, até
3 entradas com o mesmo `card_id`. Esta feature valida a lista; não a persiste e
não dá identidade às cópias.

### `DeckProblem`

União fechada de dataclasses congeladas. Cada uma tem uma propriedade `message`
que nomeia o valor ofensor.

| Classe | Campos | Mensagem contém |
|---|---|---|
| `WrongDeckSize` | `found: int`, `required: int` | quantas cartas tem e quantas devia (FR-022) |
| `TooManyCopies` | `card_id: CardId`, `count: int`, `limit: int` | o `card_id` e suas cópias (FR-023) |
| `UnknownDeckCard` | `card_id: CardId` | o `card_id` inexistente (FR-024) |

### Funções

| Função | Retorno | Contrato |
|---|---|---|
| `deck_problems(deck, catalog)` | `tuple[DeckProblem, ...]` | Todos os problemas em uma passada (FR-025). Vazia = deck válido |
| `ensure_valid_deck(deck, catalog)` | `None` | Levanta `InvalidDeckError` com todas as mensagens se houver problema |

`InvalidDeckError` guarda `problems: tuple[DeckProblem, ...]`, para o chamador
que precise da estrutura em vez do texto.

---

## Superfície pública — `cards/__init__.py`

Reexporta com `__all__` explícito: `mypy.ini` roda com `strict`, que inclui
`no_implicit_reexport` — sem `__all__` (ou `import ... as ...`), nenhum
consumidor consegue importar do pacote.

Exportados: `CardId`, `CardType`, `Card`, `Unit`, `Spell`, `SpellEffect`,
`TargetKind`, `EffectDuration`, os cinco efeitos, `CardCatalog`,
`FrozenCardCatalog`, `mvp_catalog`, os erros, `Deck`, `DeckProblem`, as três
classes de problema, `deck_problems`, `ensure_valid_deck`, `DECK_SIZE`,
`MAX_COPIES_PER_CARD`.
