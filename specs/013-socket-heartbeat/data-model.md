# Data Model: Heartbeat de aplicação nos sockets

**Feature**: `013-socket-heartbeat` | **Date**: 2026-09-13

Nada é persistido. Não há modelo, migração nem campo novo no estado da partida,
na fila ou no cache. O "dado" desta feature é a forma de duas mensagens e o estado
do socket que decide se o ping é respondido.

## Ping — mensagem do cliente

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `type` | texto | sim | exatamente `"ping"`, sensível a maiúsculas |
| `payload` | qualquer JSON | não | objeto é ecoado; qualquer outra coisa vira `{}` |
| *outros* | qualquer | não | ignorados |

Identificado por `is_ping(content)`: `content["type"] == "ping"`. Nenhum campo
invalida um ping.

## Pong — frame do servidor

| Campo | Tipo | Regra |
|---|---|---|
| `type` | texto | sempre `"pong"` |
| `payload` | objeto | `pong_payload(content)`: o `payload` do ping se for objeto, senão `{}` |

O servidor não acrescenta campo nenhum (FR-006). Se o cliente mandar um `id` no
payload, ele volta no eco. Isso não viola o princípio II: é o conteúdo do
cliente devolvido, não identidade que o servidor expõe.

### Tabela do eco

| `payload` do ping | `payload` do pong |
|---|---|
| `{"sent_at_ms": 1726000000000}` | `{"sent_at_ms": 1726000000000}` |
| `{"a": {"b": [1, 2]}}` | `{"a": {"b": [1, 2]}}` |
| `{}` | `{}` |
| ausente | `{}` |
| `null` | `{}` |
| `42` | `{}` |
| `"x"` | `{}` |
| `true` | `{}` |
| `[1, 2]` | `{}` |

## Estado do socket — quem recebe pong

`passed_socket_gates()` lê estado que os consumers já têm. Não há estado novo.

| Socket | Situação | `accepted` | `match_id` | Pong? |
|---|---|---|---|---|
| qualquer | gate de autenticação recusou (`auth_denied`, 4001) | `False` | — | não, nenhum frame |
| `ws/match/` | gate da partida recusou (`match_denied`, 44xx) | `True` | `None` | não, nenhum frame |
| `ws/match/` | aceito, em qualquer fase, inclusive `finished` | `True` | preenchido | sim |
| `ws/matchmaking/` | aceito: antes do `join_queue`, na fila, depois de recusa, depois de `match_found` | `True` | — | sim |

## O que o ping não toca

| Recurso | Leitura | Escrita |
|---|---|---|
| Partida no Redis (`MatchStore`) | não | não |
| Versão de escrita | — | não |
| Prazo da vez / do mulligan (§15) | não | não |
| Fila (`MatchmakingQueue`) | não | não |
| Decks (`PlayerDeckSource`) | não | não |
| Registro de partida / `PlayerStats` (012) | não | não |
| Presença (`presence:user:<id>`) | não | não |
| Channel layer (grupos) | não | não |
