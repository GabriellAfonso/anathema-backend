# Data Model: Decks do jogador, e o catálogo servido ao cliente

**Feature**: `011-deck-catalog-api` | **Date**: 2026-09-12

O que esta feature acrescenta: uma tabela, um payload de carta, um payload de
deck, uma entrada de fila e três códigos de recusa. O catálogo em si não muda —
`Card`, `Unit`, `Spell`, `SpellEffectShape` e as três regras de deck ficam como
estão.

## Deck do jogador (`apps/players/models/deck.py`)

```text
PlayerDeck
  pk           int         exposto como `deck_id`, nunca como `id`
  profile      FK          -> PlayerProfile, CASCADE, related_name="decks"
  name         CharField   max_length=50, não vazio após strip, repetível
  card_ids     JSONField   list[int]: ordem e repetição preservadas
  created_at   DateTime    auto_now_add
  updated_at   DateTime    auto_now
```

- `profile_id == user_id`, porque `PlayerProfile.user` é a PK (decisão 0001).
- Sem `unique_together (profile, name)`: nome repetido é aceito (FR-019).
- Sem FK para carta: carta não é linha de banco. A integridade de `card_ids`
  é a regra `UnknownDeckCard` da feature 001.
- Índice implícito da FK basta: toda consulta parte do dono.

Migração: `0002_playerdeck.py`, só `CreateModel`. Nada a migrar.

### Regras aplicadas ao salvar

| Regra | Origem | Recusa |
|---|---|---|
| nome não vazio após `strip` | esta feature (FR-018) | `{"name": ["..."]}` |
| nome até 50 caracteres | esta feature | `{"name": ["..."]}` |
| exatamente 40 cartas | feature 001, `WrongDeckSize` | `deck_problems` |
| no máximo 3 cópias | feature 001, `TooManyCopies` | `deck_problems` |
| toda carta no catálogo | feature 001, `UnknownDeckCard` | `deck_problems` |
| no máximo 20 decks (só na criação) | esta feature (FR-020) | `{"deck_limit": ...}` |

`DECK_LIMIT_PER_PLAYER = 20` mora em `apps/players/services/deck_validation.py`,
ao lado de quem o aplica.

## Payload de carta (`apps/game/card_payload.py`)

Derivado do molde congelado; nenhum campo novo é guardado em lugar nenhum.

**Unidade**

```text
card_id     int      = Unit.card_id
card_type   str      = "unit"          (CardType.UNIT.value)
name        str
energy      int
image       str
attack      int
health      int
```

**Feitiço**

```text
card_id     int      = Spell.card_id
card_type   str      = "spell"         (CardType.SPELL.value)
name        str
energy      int
image       str
description str                        para o jogador ler
effect      objeto                     para o cliente decidir a mira
```

**`effect`** — os quatro campos que `SpellEffectShape` já declara:

```text
requires_target   bool   propriedade derivada que já existe
target_kind       str    TargetKind.value: "none" | "allied_unit" | "enemy_unit"
duration          str    EffectDuration.value: "permanent" | "until_end_of_round"
declaration_only  bool   a restrição de momento da §5B/§14
```

Os conjuntos de `target_kind` e `duration` são fechados e servidos com o mesmo
texto que o motor usa (FR-006). `amount` **não** é servido (research D6).

Montado uma vez por processo (`functools.cache`), porque o catálogo é congelado
e a resposta não depende de quem pergunta.

## Payload de deck (`apps/players/deck_serializers.py`)

**Leitura**

```text
deck_id    int         source="pk", read_only
name       str
card_ids   list[int]
```

**Escrita** — `POST` e `PATCH`

```text
name       str         opcional no PATCH
card_ids   list[int]   opcional no PATCH; se vier, substitui a lista inteira
```

`PATCH` sem nenhum dos dois é recusado: não há edição vazia.

## Problema de deck, em payload (`apps/players/services/deck_problem_payload.py`)

Tradução da união `DeckProblem` da feature 001 para JSON. `match` com
`assert_never`: um problema novo no motor não chega ao cliente sem forma.

```text
WrongDeckSize    -> {"kind": "wrong_deck_size",  "found": int, "required": int,
                     "message": str}
TooManyCopies    -> {"kind": "too_many_copies",  "card_id": int, "count": int,
                     "limit": int, "message": str}
UnknownDeckCard  -> {"kind": "unknown_card",     "card_id": int, "message": str}
```

`message` é o texto que a própria feature 001 já produz — o mesmo no HTTP e no
websocket. `kind` é a chave estável que o cliente compara.

Uma recusa carrega **todos** os problemas, em `deck_problems` (FR-023).

## Entrada na fila (`apps/game/matchmaking/queue.py`)

```text
QueueEntry (frozen, slots)
  user_id  int
  deck     Deck      a lista validada no instante da entrada
```

`join(entry) -> tuple[QueueEntry, QueueEntry] | None`.

**No Redis**, dois valores por jogador na espera:

| Chave | Tipo | Conteúdo |
|---|---|---|
| `matchmaking:queue` | lista | `user_id`, em FIFO. Inalterada — é o que faz `LREM` funcionar na reentrada |
| `matchmaking:decks` | hash | `user_id` -> `card_ids` em JSON |

Os dois são escritos e lidos no mesmo script Lua, de modo que não existe
jogador na fila sem deck, nem deck sem jogador (research D10). `leave` apaga os
dois.

Serialização (`json.dumps(list(deck))` / `json.loads`) mora dentro de
`queue.py`: o formato no Redis é assunto do envoltório.

## Recusas do socket de matchmaking (`apps/game/protocol/matchmaking_refusals.py`)

| Código | Quando | Detalhes |
|---|---|---|
| `deck_not_specified` | `join_queue` sem `deck_id`, ou com `deck_id` não inteiro | — |
| `deck_not_found` | deck inexistente **ou** de outro jogador | — |
| `invalid_deck` | deck do jogador que não passa nas três regras | `deck_problems` |

`send_refusal` ganha `**details`, opcional. O socket de partida não passa nada,
e os frames da feature 009 não mudam.

## O que não muda

- `Card`, `Unit`, `Spell`, `CardType`, `CardId` — a forma da carta.
- `SpellEffectShape`, `TargetKind`, `EffectDuration` e os cinco efeitos.
- `deck_problems`, `ensure_valid_deck`, `DECK_SIZE`, `MAX_COPIES_PER_CARD` e os
  três tipos de problema.
- `MatchEntry`, `start_match`, `finish_setup` — o setup da §3.
- `Match`, o documento da partida, o `MatchStore` e o relógio da 010.
- Os frames e os códigos de recusa do socket de partida (feature 009).
