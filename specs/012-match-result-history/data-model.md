# Phase 1 — Data Model: Resultado de partida, registrado uma vez só

**Feature**: `012-match-result-history` | **Data**: 2026-09-12

Três camadas de dado, e a fronteira entre elas importa:

1. **O estado da partida** (Redis, efêmero) — ganha dois campos.
2. **O que a transição produz** (em memória, puro) — um valor só, sem ORM.
3. **O registro** (banco, permanente) — uma tabela nova, mais escrita nas
   estatísticas que já existem.

---

## 1. Estado da partida (Redis)

### `ChosenDeck` — novo

`server/apps/game/match/chosen_deck.py`, reexportado por `apps.game.match`.

```python
@dataclass(frozen=True, slots=True)
class ChosenDeck:
    name: str
    card_ids: tuple[CardId, ...]
```

Cópia congelada do deck com que o jogador entrou na fila. `frozen` porque é
registro histórico dentro de um estado mutável: a partida muda, isto não.

**Por que não `Deck` puro**: `Deck` é `tuple[CardId, ...]` e não carrega nome. O
nome é o que o jogador reconhece na análise posterior, e ele não sobrevive ao
`deck_id` (FR-028, FR-029).

### `PlayerState` — campo novo

`server/apps/game/match/player_state.py`

| Campo | Tipo | Padrão | Nota |
|---|---|---|---|
| `chosen_deck` | `ChosenDeck \| None` | `None` | O deck da entrada na fila. `None` só em documento gravado antes desta feature (D8). |

Não confundir com `PlayerState.deck`, que é a pilha de compra e **muda** durante
a partida. `chosen_deck` é a lista de 40 como ela entrou.

### `Match` — campo novo

`server/apps/game/match/match_state.py`

| Campo | Tipo | Padrão | Nota |
|---|---|---|---|
| `started_at` | `EpochMillis \| None` | `None` | Instante de criação. Estado de **transporte**, como `clock`: nenhuma regra o lê, nenhuma porta do motor o escreve. |

**Quem escreve**: `MatchmakingConsumer.open_match`, na mesma linha em que já
escreve `match.clock = opening_match_clock(...)`.

**Invariante**: `started_at is None` só acontece em documento anterior a esta
feature. Partida criada por este código sempre tem instante.

### Documento (JSON no Redis)

`server/apps/game/match/documents.py`

```python
class OptionalMatchFields(TypedDict, total=False):
    """Campos que documentos gravados antes da feature 012 não têm."""
    started_at: int | None

class MatchDocument(OptionalMatchFields):
    ...  # campos já existentes, inalterados

class OptionalPlayerFields(TypedDict, total=False):
    chosen_deck: ChosenDeckDocument | None

class ChosenDeckDocument(TypedDict):
    name: str
    card_ids: list[int]
```

`total=False` é o que faz `document.get("started_at")` valer `int | None` sob
mypy strict, sem `cast` (D8). A ida e a volta continua valendo a garantia do
cabeçalho de `serialization.py`: para todo estado válido, serializar e
desserializar devolve o original.

---

## 2. O que a transição produz (em memória)

`server/apps/game/history/finished_match.py` — puro, sem ORM, sem Redis.

```python
@dataclass(frozen=True, slots=True)
class FinishedSide:
    user_id: int
    final_nexus: int
    deck_name: str
    deck_card_ids: tuple[CardId, ...]


@dataclass(frozen=True, slots=True)
class FinishedMatch:
    match_id: str
    reason: MatchEndReason
    winner: FinishedSide
    loser: FinishedSide
    started_at: EpochMillis
    ended_at: EpochMillis
    final_round: int

    @property
    def duration_seconds(self) -> int:
        return max(0, (self.ended_at - self.started_at) // 1000)
```

**Derivação**, toda a partir do estado — nenhuma decisão nova:

| Campo | De onde |
|---|---|
| `match_id` | `after.match_id` |
| `reason` | `after.outcome.reason` |
| `loser` | o `PlayerState` de `after.outcome.defeated_user_id` |
| `winner` | `after.opponent_of(defeated_user_id)` — FR-006, sem segunda fonte |
| `final_nexus` | `player.nexus` de cada lado |
| `deck_name` / `deck_card_ids` | `player.chosen_deck`, ou `""` / `()` se ausente |
| `started_at` | `after.started_at`, ou `ended_at` se ausente (duração 0) |
| `ended_at` | o `now` de quem gravou |
| `final_round` | `after.round_number` |

**A porta**:

```python
def finished_match(
    before: Match, after: Match, ended_at: EpochMillis
) -> FinishedMatch | None:
    """O registro a gravar, ou None se esta gravação não terminou a partida."""
```

`None` para toda observação: uma partida que já estava terminada em `before`
devolve `None`, quantas vezes for lida (FR-007).

---

## 3. O registro (banco)

### `MatchRecord` — tabela nova

`server/apps/game/models/match_record.py`
Migração: `apps/game/migrations/0001_initial.py` (o app não tem nenhuma hoje).

| Campo | Tipo | Regras |
|---|---|---|
| `match_id` | `CharField(max_length=64)` | **`unique=True`** — é o que faz a corrida perder em vez de duplicar (FR-004, FR-009). Indexado pela unicidade. |
| `winner` | `FK(PlayerProfile, SET_NULL, null=True, related_name="matches_won")` | `winner_id` **é** o `user_id` (decisão 0001). Sem coluna espelho (D5). |
| `loser` | `FK(PlayerProfile, SET_NULL, null=True, related_name="matches_lost")` | idem, `related_name="matches_lost"`. |
| `end_reason` | `CharField(max_length=20, choices=…)` | Valores de `MatchEndReason`: `nexus_depleted`, `forfeit`. Conjunto fechado (FR-005). |
| `started_at` | `DateTimeField` | Convertido de `EpochMillis`, UTC. |
| `ended_at` | `DateTimeField` | Ordena o histórico (`-ended_at`). |
| `duration_seconds` | `PositiveIntegerField` | Guardado, não calculado na leitura: `started_at` pode ser o mesmo que `ended_at` em partida anterior à feature, e o valor registrado é o que somou em `play_time`. |
| `final_round` | `PositiveIntegerField` | Desistência no mulligan registra `1` (rodada 1 é o padrão de `Match.round_number`). |
| `winner_final_nexus` | `IntegerField` | Sem teto e pode ser negativo: o Nexus não tem teto, e o dano pode passar de zero. |
| `loser_final_nexus` | `IntegerField` | idem. |
| `winner_deck_name` | `CharField(max_length=50, blank=True)` | Mesmo teto de `PlayerDeck.name`. Vazio = documento anterior à feature. |
| `loser_deck_name` | `CharField(max_length=50, blank=True)` | idem. |
| `winner_deck_card_ids` | `JSONField(default=list)` | Lista de `card_id`, na ordem da entrada na fila. |
| `loser_deck_card_ids` | `JSONField(default=list)` | idem. |

**Meta**:

```python
class Meta:
    verbose_name = "Match Record"
    verbose_name_plural = "Match Records"
    indexes = [
        models.Index(fields=["winner", "-ended_at"]),
        models.Index(fields=["loser", "-ended_at"]),
    ]
```

Os dois índices são o que a listagem usa: ela filtra por um lado ou pelo outro e
ordena por `-ended_at`.

**`__str__`**: `f"{self.match_id} ({self.end_reason})"`.

### `PlayerStats` — escrita, sem mudança de esquema

`server/apps/players/models/player.py` fica exatamente como está. O que muda é
que passa a ser escrito:

| Campo | Vencedor | Derrotado |
|---|---|---|
| `matches_played` | `F(...) + 1` | `F(...) + 1` |
| `wins` | `F(...) + 1` | — |
| `losses` | — | `F(...) + 1` |
| `play_time` | `F(...) + duration_seconds` | `F(...) + duration_seconds` |

Segundos (D12). `F()` para não perder incremento concorrente (D4, FR-013).

**Transação**: as duas escritas de estatística e a inserção do registro dentro do
mesmo `transaction.atomic()` (FR-011). Um perfil sem `PlayerStats` — conta criada
fora do registro — não impede o registro: o `update()` filtrado afeta 0 linhas e
segue.

---

## Relações

```
PlayerProfile ──< matches_won  (MatchRecord.winner, SET_NULL)
PlayerProfile ──< matches_lost (MatchRecord.loser,  SET_NULL)
PlayerProfile ──1 PlayerStats  (já existe)
```

Uma partida registrada aponta para dois perfis. Apagar um perfil anula a ponta
dele e deixa a linha inteira de pé — é o que mantém o histórico do outro legível
(FR-022).

---

## Transições de estado

O registro **não tem** transição: é criado uma vez e nunca é alterado nem
apagado por código desta feature. Não há `updated_at`, e nenhuma rota escreve nele.

A transição que importa é a da partida, e ela é do motor:

```
outcome is None  ──(_finish_match, engine/victory.py)──>  outcome is not None
                                                          phase = FINISHED
```

Esta feature observa essa transição uma vez, na gravação que a produziu, e nunca
mais.
