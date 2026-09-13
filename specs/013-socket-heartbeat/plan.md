# Implementation Plan: Heartbeat de aplicação nos sockets

**Branch**: `013-socket-heartbeat` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-socket-heartbeat/spec.md`

## Summary

O cliente manda `{"type": "ping", "payload": ...}` e o servidor responde
`{"type": "pong", "payload": <eco ou {}>}`, só para aquele socket, nos dois
sockets, sem tocar partida, fila, deck, registro, presença ou channel layer.

A feature é pequena em código e estreita em lugar. Quase tudo depende de **onde**
o ping é tratado:

1. **No `BaseConsumer.receive`, depois da decodificação e antes de
   `receive_json`** (D1). É o último trecho comum aos dois consumers: o
   `MatchConsumer` substitui `receive_json`, mas não `receive`. O ping nunca
   chega ao parser de jogadas, então não tem como virar comando, versão ou
   `match_update`.
2. **A regra é pura, em `protocol/heartbeat.py`** (D2): `is_ping` e
   `pong_payload`. O consumer só as liga ao `send_event`.
3. **Só socket que passou pelos gates responde** (D3):
   `passed_socket_gates()` lê o `accepted` do base, e o `MatchConsumer`
   acrescenta `match_id is not None`. Ping em socket recusado não recebe frame
   nenhum, porque frame depois do close é o `RuntimeError` que
   `test_base_consumer_lifecycle.py` já registra.

A presença (`set_heartbeat`) não é tocada, nem para ligar nem para apagar (D5).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Django Channels 4.3 (`AsyncJsonWebsocketConsumer`),
Uvicorn 0.52. `websockets`, já usado pela fumaça.

**Storage**: nenhum. Por construção, o ping não lê nem grava Redis, banco ou
cache.

**Testing**: pytest 9.1 + pytest-asyncio 1.4, `cd server && pytest`. Testes de
socket sobre `WebsocketTestClient`, com `FakeMatchStore`, `FakeMatchmakingQueue`,
`FakePlayerDeckSource`, `FakeFinishedMatchRecorder` e o `InMemoryChannelLayer` do
`conftest.py`.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`), Uvicorn
com 4 workers. O pong sai do mesmo worker que recebeu o ping, então não há nada
entre workers.

**Project Type**: web service. Backend websocket; o cliente Unity não está neste
repositório.

**Performance Goals**: pong em menos de 1 s com servidor local sem carga
(SC-010). O caminho é decodificar, comparar um texto e escrever um frame, sem
I/O além do próprio socket.

**Constraints**: nenhum acesso a armazenamento no caminho do ping; nenhum frame
depois do close; `receive` dentro de 20 linhas; nenhum teste de websocket toca o
banco (`apps/game/tests/conftest.py`); mypy `strict` com `warn_unreachable`;
`scripts/smoke_match.py` abaixo de 500 linhas.

**Scale/Scope**: um módulo novo de protocolo (~40 linhas), um método dividido e
dois métodos novos no `BaseConsumer`, um override de uma linha no `MatchConsumer`,
um fake e um helper de socket de teste, cinco arquivos de teste, um módulo de
fumaça, três arquivos de contrato.

## Constitution Check

*GATE: passa antes da Phase 0 e re-verificado depois da Phase 1.*

| Princípio | Como esta feature cumpre |
|---|---|
| **I. Notas de decisão são a fonte da verdade** | Nada de domínio muda. A decisão 0001 não é afetada: o ping não carrega identidade. O `Backend/TODO.md` é respeitado: presença continua adiada (D5), e ao fim a entrada ganha uma linha registrando que o ping cliente→servidor existe. Nenhuma nota de decisão nova. |
| **II. Identidade nomeada, nunca `id` pelado** | O pong não tem campo do servidor. O eco é o conteúdo do cliente devolvido; um `id` que o cliente mande volta, mas não é identidade exposta pelo servidor (data-model.md). |
| **III. Tipos explícitos, mypy strict** | `is_ping(content: Mapping[str, object]) -> bool`, `pong_payload(content: Mapping[str, object]) -> dict[str, object]`, `passed_socket_gates(self) -> bool`. Nenhum `Any`, nenhum `cast` novo, nenhuma relaxação nova no `mypy.ini`. |
| **IV. Unidades pequenas, uma responsabilidade** | A forma do ping fica em `protocol/heartbeat.py`, o envio no consumer. O `receive`, que já tem 20 linhas de corpo, é dividido: `decode_client_frame` recusa e devolve o objeto; `receive` decide entre ping e `receive_json`. `smoke_match.py` (460 linhas) ganha um módulo irmão em vez de passar de 500 (D10). |
| **V. Comportamento testado com fakes nomeados** | Toda função nova tem teste. "Não lê a partida" é provado por `AccessCountingMatchStore`, subclasse nomeada de `FakeMatchStore` (D8). Os testes ficam em `apps/game/tests/`. |
| **Stack fixada** | Nenhuma dependência nova. |
| **Injeção de dependência** | Nenhuma dependência nova a injetar. `heartbeat.py` é função pura importada como `parse_client_message` já é, e não I/O. |
| **Biblioteca de terceiro atrás de interface própria** | O ping usa só `send_event`, que já é a interface do projeto sobre o `send_json` do Channels. |
| **Logging** | Nenhum log por ping (D7). Nenhuma falha nova a registrar. |
| **Comentários** | Os comentários existentes do `receive` e do `receive_json` são preservados na divisão. O ramo do ping explica o porquê (o `MatchConsumer` não passa pelo roteamento) e aponta para o contrato. |

**Resultado**: passa. Nenhuma violação a justificar; a seção *Complexity
Tracking* foi removida.

**Re-verificação pós-Phase 1**: passa. O desenho não duplica a regra (D1, D2), não
cria estado de socket novo (D3 lê o que existe), não abre I/O no caminho do ping
(D4) e não resolve em passagem o item de presença do `TODO.md` (D5).

## Project Structure

### Documentation (this feature)

```text
specs/013-socket-heartbeat/
├── plan.md                      # Este arquivo
├── research.md                  # Phase 0 — 11 decisões com alternativas rejeitadas
├── data-model.md                # Phase 1 — forma do ping e do pong, quem recebe pong
├── quickstart.md                # Phase 1 — como provar, mapeado aos SCs
├── contracts/
│   └── heartbeat_messages.md    # o contrato dos dois sockets
├── checklists/
│   └── requirements.md
└── tasks.md                     # Phase 2 — criado por /speckit-tasks

specs/009-match-protocol/contracts/client_messages.md        # + nota: ping existe (FR-018)
specs/011-deck-catalog-api/contracts/matchmaking_messages.md # + nota: ping existe (FR-018)
```

### Source Code (repository root)

```text
server/apps/game/
├── protocol/
│   ├── heartbeat.py                         # NOVO — PING, PONG, is_ping, pong_payload
│   └── __init__.py                          # reexporta; docstring cita o módulo
├── consumers/
│   ├── base.py                              # receive dividido: decode_client_frame,
│   │                                        #   answer_ping, passed_socket_gates
│   └── match.py                             # + passed_socket_gates (match_id preenchido)
└── tests/
    ├── access_counting_match_store.py       # NOVO — FakeMatchStore que conta acessos
    ├── test_heartbeat.py                    # NOVO — a regra pura
    ├── matchmaking_sockets.py               # NOVO — abrir o socket de fila com os fakes
    ├── heartbeat_sockets.py                 # NOVO — qualquer socket aceito; expect_pong
    ├── test_match_consumer_heartbeat.py     # NOVO — socket de partida (US1)
    ├── test_matchmaking_heartbeat.py        # NOVO — socket de matchmaking (US2)
    ├── test_heartbeat_echo.py               # NOVO — eco nos dois sockets (US3)
    └── test_heartbeat_gates.py              # NOVO — gates com ping; `pong` recusado

scripts/
├── smoke_heartbeat.py                       # NOVO — ping, eco, contagem, latência
└── smoke_match.py                           # usa smoke_heartbeat nos dois sockets
```

**Structure Decision**: a regra entra no pacote `protocol`, que já guarda a forma
das mensagens dos dois sockets. O envio entra no `BaseConsumer`, que a nota
`Backend/Consumers/BaseConsumer.md` define como o lugar do "contrato mínimo
comum" e do roteamento de mensagens recebidas. Nenhum arquivo de `matchmaking.py`
muda: ele herda o comportamento do base. `match.py` muda em um método só.

## Phase 0 — Research

Concluída. Onze decisões em [research.md](research.md):

| # | Decisão |
|---|---|
| D1 | O ping é reconhecido no `BaseConsumer.receive`, depois da decodificação |
| D2 | A regra é pura, em `protocol/heartbeat.py`: `is_ping` e `pong_payload` |
| D3 | Ping em socket recusado pelo gate é descartado, sem frame (`passed_socket_gates`) |
| D4 | O pong sai pelo `send_event` do próprio socket, nunca pelo channel layer |
| D5 | O ping não renova presença, e as peças mortas ficam |
| D6 | Ordem dos pongs garantida pelo consumer, sem fila própria |
| D7 | Sem limite de taxa, sem limite de tamanho próprio, sem log |
| D8 | "Não lê a partida" provado por `AccessCountingMatchStore` |
| D9 | Testes de matchmaking pelo socket de verdade; `match_found` por `group_send` |
| D10 | A fumaça ganha pings num módulo irmão, sempre ligados |
| D11 | Contrato novo, notas na 009 e na 011, catálogo de recusas intocado |

Nenhum `NEEDS CLARIFICATION` restante.

## Phase 1 — Design & Contracts

Concluída.

- [data-model.md](data-model.md): a forma do ping e do pong, a tabela do eco, a
  tabela de estado do socket e a matriz do que o ping não toca.
- [contracts/heartbeat_messages.md](contracts/heartbeat_messages.md): o contrato
  dos dois sockets.
- Notas acrescentadas ao fim de `specs/009-match-protocol/contracts/client_messages.md`
  e `specs/011-deck-catalog-api/contracts/matchmaking_messages.md`.
- [quickstart.md](quickstart.md): suíte, testes da feature mapeados aos SCs,
  fumaça e conferência manual.
- Contexto do agente: os marcadores `SPECKIT` do `CLAUDE.md` apontam para este
  plano.

### Forma do `receive` depois da mudança

Só para fixar a ordem. O código é da implementação.

```text
receive(text_data, bytes_data)
  content = decode_client_frame(text_data)   # recusa binário / não-JSON / não-objeto → None
  se content é None: retorna
  se is_ping(content): answer_ping(content); retorna
  receive_json(content)                      # inalterado: roteamento do base ou parser da partida

answer_ping(content)
  se não passed_socket_gates(): retorna      # nada depois do close
  send_event(type=PONG, payload=pong_payload(content))
```

### Ordem de implementação sugerida

Quatro fatias, cada uma verde antes da seguinte:

0. **A fumaça, primeiro**: `black` sozinho no `smoke_match.py` (o único arquivo
   que `black --check server/ scripts/` reprova hoje), depois
   `scripts/smoke_heartbeat.py` e a integração. Rodar contra o servidor sem
   mudança: tem de falhar. Fazer isso antes do código de servidor dispensa
   subir `dev` numa worktree à parte.
1. **A regra**: `protocol/heartbeat.py` e `test_heartbeat.py`. Puro, sem socket.
   Prova: a matriz do eco e o `is_ping` exato.
2. **Os sockets**: a divisão do `receive`, `answer_ping`,
   `passed_socket_gates` e o override no `MatchConsumer`;
   `AccessCountingMatchStore`, `matchmaking_sockets.py` e os quatro arquivos de
   teste de socket. Prova: SC-001 a SC-008, e a suíte existente inteira verde
   **sem alteração**. É a única fatia que mexe em código existente, e o
   `receive` é o caminho de toda mensagem dos dois sockets. O risco de regressão
   está aqui.
3. **A prova de ponta e os papéis**: a fumaça contra esta branch (tem de passar,
   SC-009 e SC-010); as linhas no `Backend/TODO.md` e no
   `Backend/Consumers/BaseConsumer.md`.
