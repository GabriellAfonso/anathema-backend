# Contrato interno — A porta de gravação do resultado

**Feature**: `012-match-result-history`

Não é contrato de rede: é a fronteira entre o caminho de partida (assíncrono, sem
banco) e a persistência. Existe porque `apps/game/tests/conftest.py` registra que
**nenhum teste de websocket toca o banco**, e uma escrita de ORM alcançável do
consumer quebraria essa garantia na suíte inteira (D9).

Mesma forma de `PlayerDeckSource`, e pela mesma razão.

---

## `FinishedMatchRecorder`

`server/apps/game/history/recorder.py`

```python
class FinishedMatchRecorder(Protocol):
    """Grava o resultado de uma partida terminada. Uma vez, e só uma."""

    async def record(self, finished: FinishedMatch) -> bool:
        """`True` se esta chamada gravou; `False` se a partida já estava registrada."""
        ...
```

### Garantias que toda implementação deve cumprir

1. **Idempotente por `match_id`**: chamar duas vezes com o mesmo `match_id` grava
   uma vez. A segunda devolve `False` e não altera nada — nem registro, nem
   estatística (FR-001, FR-009).
2. **Atômica**: o registro e as duas atualizações de estatística acontecem juntos
   ou nenhum acontece (FR-011).
3. **Não levanta por corrida**: perder a disputa é `False`, não exceção. Só falha
   real (banco fora do ar) levanta.
4. **Não decide nada**: recebe o valor já derivado do estado. Não olha partida, não
   olha Redis, não escolhe vencedor.

### `DatabaseFinishedMatchRecorder`

A implementação de verdade. Estrutura:

```
record(finished)                     # async, embrulha a síncrona
└── _write(finished)                 # @database_sync_to_async, @transaction.atomic
    ├── _insert_record(finished)     # savepoint próprio; IntegrityError -> False
    └── _bump_stats(finished)        # dois update() com F(), vencedor e derrotado
```

O savepoint em `_insert_record` é obrigatório: um `IntegrityError` levantado
direto dentro de `atomic()` marca a transação para rollback, e a atualização de
estatística seguinte levantaria `TransactionManagementError` (D3).

`database_sync_to_async` chega sem stubs — o decorator leva `# type:
ignore[untyped-decorator]` com o comentário de sempre, como em
`player_queries.py` e `deck_queries.py`.

### `FakeFinishedMatchRecorder`

`server/apps/game/tests/fake_finished_match_recorder.py`

Classe nomeada, como manda a constituição — não stub inline, não lambda.

```python
class FakeFinishedMatchRecorder:
    """Guarda o que foi gravado, em memória, com a mesma regra de unicidade."""

    def __init__(self) -> None:
        self.recorded: list[FinishedMatch] = []

    async def record(self, finished: FinishedMatch) -> bool: ...
```

`recorded` é o que o teste inspeciona: quantos registros, de qual partida, com
qual vencedor. A regra de unicidade por `match_id` é reproduzida aqui para que o
teste de socket exercite o mesmo contrato que a produção.

---

## Quem injeta

| Consumidor | Parâmetro do construtor | Padrão |
|---|---|---|
| `MatchConsumer` | `recorder: FinishedMatchRecorder \| None = None` | `DatabaseFinishedMatchRecorder()` |
| `MatchClockTicker` | `recorder: FinishedMatchRecorder` (obrigatório, palavra-chave) | injetado por `core/asgi.py` |

`MatchConsumer` aceita `None` porque o Channels instancia o consumer e os testes
passam por `as_asgi(recorder=...)` — é o padrão que `matches=`, `catalog=`,
`randomness=` e `clock=` já seguem. O ticker já exige todas as dependências por
palavra-chave e ganha mais uma.

---

## O disparo

`server/apps/game/history/record_finished_match.py`

```python
async def record_finished_match(
    recorder: FinishedMatchRecorder,
    before: Match,
    stored: StoredMatch,
    *,
    ended_at: EpochMillis,
) -> None:
    """Grava o resultado se esta gravação terminou a partida. Nunca levanta."""
```

Duas linhas de comportamento:

1. `finished = finished_match(before, stored.match, ended_at)`; se `None`, volta
   sem fazer nada — não foi transição (FR-007).
2. `await recorder.record(finished)` dentro de `try`, com toda exceção capturada e
   registrada em log estruturado (FR-016).

**Chamado por** — os dois únicos caminhos que podem terminar uma partida, sempre
**depois** da entrega do estado final aos jogadores:

- `MatchConsumer.play`, com `ended_at=self.clock.now_ms()`
- `MatchClockTicker._expire`, com `ended_at=now`

**Não chamado por**: `MatchConsumer.connect` (observação), `_warn` do ticker (a
marca do aviso não passa pelo motor), nem nada dentro de `MatchStore.mutate` — o
compare-and-swap reaplica a mudança numa retentativa, e uma escrita de banco lá
dentro aconteceria duas vezes (FR-008).
