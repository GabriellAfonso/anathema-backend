# Contrato: o socket de matchmaking

**Feature**: `011-deck-catalog-api`

`ws/matchmaking/`, autenticado como hoje. O que muda: **conectar não entra mais
na fila**. O cliente entra dizendo com qual deck joga.

## O que o cliente manda

### `join_queue`

```json
{"type": "join_queue", "payload": {"deck_id": 4}}
```

| Campo | Tipo | Obrigatório |
|---|---|---|
| `deck_id` | int | sim |

O servidor, nesta ordem:

1. confere que `deck_id` veio e é inteiro;
2. busca o deck **do jogador autenticado** com aquele identificador;
3. valida a lista contra o catálogo do momento;
4. **só então** põe o jogador na fila.

Toda recusa acontece antes do passo 4: um jogador recusado nunca ocupa lugar na
fila, nenhum par é consumido, e nenhum oponente perde tempo de fila por um
problema que não é dele.

A lista validada no passo 3 é o que viaja com a entrada, e é o que a partida
usa. Editar ou apagar o deck depois disso não muda nem a fila nem a partida.

Mandar `join_queue` de novo substitui a entrada anterior: vale o deck da
mensagem mais recente, e o jogador vai para o fim da fila.

## O que o servidor manda

### `match_found` — inalterado

```json
{
  "type": "match_found",
  "payload": {
    "self": {"user_id": 7, "nickname": "one", "icon": "default", "level": 1},
    "opponent": {"user_id": 9, "nickname": "two", "icon": "default", "level": 1},
    "match_id": "..."
  }
}
```

### `message_refused`

```json
{
  "type": "message_refused",
  "payload": {
    "error": "payload is {}: expected {'deck_id': <int>}",
    "code": "deck_not_specified"
  }
}
```

**A recusa não fecha o socket.** O cliente corrige e manda `join_queue` de novo.

| `code` | Quando |
|---|---|
| `deck_not_specified` | `join_queue` sem `deck_id`, ou com `deck_id` que não é inteiro |
| `deck_not_found` | o deck não existe, **ou** é de outro jogador |
| `invalid_deck` | o deck é do jogador e não passa nas três regras |
| `malformed_message` | frame que não é JSON, ou não é objeto (feature 009) |
| `unknown_message_type` | `type` sem handler neste socket (feature 009) |

`deck_not_found` é **o mesmo código e o mesmo texto** para deck inexistente e
para deck de outro jogador:

```json
{
  "type": "message_refused",
  "payload": {
    "error": "deck_id 4 is not a deck of user 9",
    "code": "deck_not_found",
    "deck_id": 4
  }
}
```

O `deck_id` é o que o cliente pediu, ecoado de volta. Nada mais na recusa
depende de o deck existir: o mesmo pedido, do mesmo jogador, recebe esta
resposta byte a byte tanto quando o deck é de outro quanto quando não existe
para ninguém.

`invalid_deck` carrega os problemas estruturados ao lado do texto:

```json
{
  "type": "message_refused",
  "payload": {
    "error": "card_id 12 appears 4 times, limit is 3",
    "code": "invalid_deck",
    "deck_problems": [
      {
        "kind": "too_many_copies",
        "card_id": 12,
        "count": 4,
        "limit": 3,
        "message": "card_id 12 appears 4 times, limit is 3"
      }
    ]
  }
}
```

A forma de `deck_problems` é a mesma do HTTP — ver
[`http_decks.md`](./http_decks.md). Vários problemas vêm juntos, e `error` é a
junção das mensagens por `"; "`.

### `matchmaking_failed` — inalterado

Continua cobrindo o que já cobria: perfil ausente de um dos pareados, e deck
recusado pela última guarda do setup. Não é o caminho das recusas de deck
acima, que acontecem antes da fila.

## Desconexão

Fechar o socket tira o jogador da fila, e o deck da entrada sai junto.

## O que não muda

- O envelope `{"type": ..., "payload": {...}}`.
- O gate de autenticação e o close code `4001`.
- O `match_found`, e o cliente abrindo `ws/match/` em seguida.
- Todo o protocolo do socket de partida (feature 009) e o relógio (feature 010).

## `ping` (feature 013)

`{"type": "ping", "payload": {...}}` existe neste socket e **não é recusado**:
antes do `join_queue`, na fila, depois de uma recusa e depois do `match_found`.
Não mexe na fila nem consulta deck. O servidor responde `pong` só a este socket.
Ver [013 — heartbeat_messages.md](../../013-socket-heartbeat/contracts/heartbeat_messages.md).
