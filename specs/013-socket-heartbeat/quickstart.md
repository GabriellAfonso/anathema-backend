# Quickstart: provar o heartbeat

**Feature**: `013-socket-heartbeat`

Como validar que a feature funciona. A forma das mensagens está em
[contracts/heartbeat_messages.md](contracts/heartbeat_messages.md); o estado que
decide quem recebe pong, em [data-model.md](data-model.md).

## Pré-requisitos

- `venv` com `server/requirements-dev.txt` instalado.
- Para a fumaça: `docker compose up` rodando (Redis, migração e uvicorn).

## 1. Suíte e portas de qualidade

```sh
cd server && pytest
cd server && mypy
black --check server/ scripts/
```

**Esperado**: tudo verde, e nenhum teste existente alterado (SC-011).

## 2. Só os testes desta feature

```sh
cd server && pytest apps/game/tests/test_heartbeat.py \
                    apps/game/tests/test_match_consumer_heartbeat.py \
                    apps/game/tests/test_matchmaking_heartbeat.py \
                    apps/game/tests/test_heartbeat_echo.py \
                    apps/game/tests/test_heartbeat_gates.py
```

| Cenário | Arquivo | Critério |
|---|---|---|
| Matriz do eco: objeto aninhado ecoado; ausente, `null`, número, texto, booleano e lista viram `{}` | `test_heartbeat.py` | SC-002 |
| `is_ping` exato: `ping` sim; `pong`, `Ping`, `PING`, `" ping"`, ausente e não-texto não | `test_heartbeat.py` | FR-013, FR-014 |
| Eco pelo socket de verdade, nos dois: marcador, objeto aninhado, payload que não é objeto, campos a mais | `test_heartbeat_echo.py` | SC-002, FR-006 |
| 50 pings viram 50 pongs em ordem, sem recusa, nos dois sockets | `test_match_consumer_heartbeat.py`, `test_matchmaking_heartbeat.py` | SC-001 |
| Ping em `mulligan`, `action`, `declaration`, `combat` e `finished`: zero acesso ao store, snapshot, versão e prazos iguais, nada no outro socket | `test_match_consumer_heartbeat.py` | SC-003 |
| Ping depois de desistência: pong, e o `FakeFinishedMatchRecorder` continua com um registro | `test_match_consumer_heartbeat.py` | SC-004 |
| Ping antes do `join_queue`, na fila, depois de recusa e depois de `match_found`: `queue.waiting` e `decks.asked` iguais | `test_matchmaking_heartbeat.py` | SC-005 |
| Mesmo usuário com dois sockets de partida: só o que mandou recebe pong | `test_match_consumer_heartbeat.py` | SC-006 |
| Gate de autenticação e os três gates da partida, com ping: mesmo frame, mesmo close code, nada depois | `test_heartbeat_gates.py` | SC-007 |
| `pong` do cliente recusado com `unknown_message_type` nos dois sockets | `test_heartbeat_gates.py` | SC-008 |

## 3. Partida de fumaça contra o servidor local

```sh
docker compose up -d
venv/Scripts/python scripts/smoke_match.py
venv/Scripts/python scripts/smoke_match.py --spells
venv/Scripts/python scripts/smoke_match.py --forfeit-at 3
```

**Esperado** (SC-009, SC-010):

- uma linha por bot com pings mandados, pongs recebidos e maior latência medida;
- pongs igual a pings nos dois bots;
- nenhuma recusa `unknown_message_type`;
- latência abaixo de 1 s com servidor local sem carga;
- `== OK`, com a partida no histórico exatamente uma vez para cada jogador.

Com o servidor **antes** desta feature, a fumaça tem de falhar: o primeiro ping
no socket de fila volta como `message_refused`. Rodar uma vez antes de aplicar
a mudança de servidor (tarefa T005) é o que prova que a fumaça testa o que diz
testar.

## 4. Conferência manual (opcional)

Com um token válido de `/accounts/login/`:

```sh
venv/Scripts/python -m websockets "ws://localhost:8000/ws/matchmaking/?token=<token>"
> {"type": "ping", "payload": {"n": 1}}
< {"type": "pong", "payload": {"n": 1}}
> {"type": "ping", "payload": 42}
< {"type": "pong", "payload": {}}
> {"type": "pong"}
< {"type": "message_refused", "payload": {"error": "...", "code": "unknown_message_type"}}
```
