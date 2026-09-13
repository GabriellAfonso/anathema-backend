# Contrato: ping e pong

**Feature**: `013-socket-heartbeat`

Vale igual nos dois sockets: `ws/matchmaking/` e `ws/match/?matchId=<uuid>`.

Para que serve: o cliente mede silêncio. Ele manda ping periodicamente e declara
a conexão morta quando fica tempo demais sem receber frame nenhum. O ping/pong do
protocolo WebSocket não serve para isso, porque o `ClientWebSocket` do .NET o
responde sozinho e não o mostra para a aplicação.

## O que o cliente manda

```json
{"type": "ping"}
{"type": "ping", "payload": {"sent_at_ms": 1726000000000}}
```

| Campo | Tipo | Obrigatório |
|---|---|---|
| `type` | `"ping"`, exato | sim |
| `payload` | qualquer JSON | não |

Campos a mais são ignorados.

## O que o servidor responde

```json
{"type": "pong", "payload": {"sent_at_ms": 1726000000000}}
```

- **Um pong por ping**, na ordem dos pings.
- **Só para o socket que mandou.** Nem para outro socket do mesmo usuário, nem
  para o oponente.
- **Eco**: se o `payload` do ping é objeto, o do pong é o mesmo objeto, em todos
  os níveis. Ausente, `null`, número, texto, booleano ou lista viram `{}`.
- **O servidor não acrescenta nada.** Nem instante, nem identificador. Para
  medir latência, o cliente põe o próprio marcador no ping.

Entre um ping e o pong dele podem chegar outros frames, como um `match_update`
causado pelo oponente. Case pelo `type`, não pela posição.

## O ping nunca é recusado

Nenhum `message_refused` sai de um ping, qualquer que seja o `payload`. O catálogo
de códigos de recusa ([009 — refusal_codes.md](../../009-match-protocol/contracts/refusal_codes.md))
não muda.

## O que o ping não faz

No socket de partida:

- não lê nem grava a partida;
- não cria versão;
- não gera `match_update` para ninguém;
- não conta como ação, não estende o prazo da vez nem o do mulligan;
- não atesta que a partida existe: uma partida expirada ainda responde pong, e a
  próxima jogada recebe `match_not_found`, como hoje.

No socket de matchmaking:

- não entra, não sai e não muda de lugar na fila;
- não consulta deck;
- não gera `match_found` nem `matchmaking_failed`.

Nos dois: não renova presença de usuário e não registra nada.

## Quando funciona

A qualquer momento de um socket que passou pelos gates:

| Socket | Momentos |
|---|---|
| `ws/matchmaking/` | antes do `join_queue`, na fila, depois de uma recusa, depois do `match_found` |
| `ws/match/` | todas as fases: `mulligan`, `action`, `declaration`, `combat`, `finished` |

## Quando não há pong

Socket recusado pelo gate fecha como hoje, e o ping não recebe resposta:

| Gate | Frame | Close code |
|---|---|---|
| autenticação | `auth_denied` | 4001 |
| partida: sem `matchId` | `match_denied` | 4400 |
| partida: não joga a partida | `match_denied` | 4403 |
| partida: partida inexistente | `match_denied` | 4404 |

## O que continua recusado

| Mensagem | Resposta |
|---|---|
| `{"type": "pong"}` | `message_refused`, `unknown_message_type` |
| `{"type": "Ping"}`, `{"type": "PING"}`, `{"type": " ping"}` | `message_refused`, `unknown_message_type` |
| frame binário, texto que não é JSON, JSON que não é objeto | `message_refused`, `malformed_message` |

## O que não muda

- O envelope `{"type": ..., "payload": {...}}`.
- Os gates e seus close codes.
- Toda outra mensagem dos dois sockets (features 009, 010, 011, 012).
- O ping/pong do protocolo WebSocket feito pelo servidor.
