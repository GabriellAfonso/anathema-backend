# Implementation Plan: Protocolo de partida

**Branch**: `009-match-protocol` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-match-protocol/spec.md`

## Summary

O socket de partida passa a receber jogadas, passá-las pelo motor, gravar pelo
compare-and-swap que já existe, e entregar a cada socket a partida montada para
o dono dele, com a descrição do que aconteceu e a posição da mudança.

O motor não muda. Tudo que é novo mora num pacote de transporte novo,
`apps/game/protocol/`, sem I/O, e o consumer só costura. Cinco decisões carregam
a feature.

**A mensagem vira comando antes de tocar a partida** (D1). `parse_client_message`
recebe o JSON cru e o `user_id` do socket e devolve um `ClientCommand` — os nove
braços de `PlayerAction`, mais `MulliganCommand` e `ForfeitCommand` — ou levanta
`MalformedMessageError` com código. O autor sai do socket, nunca do payload.

**Uma mutação por comando, e o fim do setup dentro dela** (D4).
`apply_command` despacha: ação vai a `submit_action`; mulligan vai a
`record_mulligan` e, se o setup fechou, a `begin_round_cycle` na mesma chamada;
desistência vai a `forfeit`. O consumer chama isso dentro de `MatchStore.mutate`,
guardando o estado de antes de cada tentativa — só a tentativa gravada vale.

**A descrição do que aconteceu é a diferença entre o antes e o depois** (D5).
`describe_change(before, after, command, recipient)` compara as duas partidas e
produz eventos já recortados para o destinatário: a jogada, e o que ela causou —
dano, mortes, Nexus, rodada nova, compras, fim da partida. Não exige porta nova
no motor, e o recorte por destinatário acontece num lugar só.

**Cada jogador recebe pelo grupo dele, e o frame já sai montado para ele** (D6).
Depois de gravar, o worker de quem jogou monta um `match_update` para cada um
dos dois jogadores e manda ao grupo de usuário daquele jogador. Nunca uma visão
pronta ao grupo da partida — é a armadilha que a spec nomeia. O handler do
consumer confere o `match_id` antes de encaminhar.

**A posição da mudança é a versão de escrita do Redis** (D7). `mutate` e a nova
`get_stored` devolvem `StoredMatch(match, version)`; `match_start` e
`match_update` levam a versão, e o cliente descarta a menor.

As recusas têm um catálogo fechado de códigos, um por espécie (D2), e um teste
que varre toda subclasse de `IllegalActionError` para garantir que nenhuma fica
sem código e que nenhum código se repete.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Django Channels 4.3 (consumer, channel layer),
channels_redis 4.3, redis-py async. Nenhuma dependência nova.

**Storage**: Redis, pelo `MatchStore` existente. Muda a superfície: `mutate`
devolve `StoredMatch`, e entra `get_stored`. Os scripts Lua passam a devolver a
versão nova. O documento da partida não muda.

**Testing**: pytest 9.1 + pytest-asyncio, `cd server && pytest`. Os testes de
consumer usam `WebsocketTestClient`, `FakeMatchStore` e o `InMemoryChannelLayer`
do `conftest.py`. `test_match_store.py` usa Redis (roda no container).

**Target Platform**: servidor Linux, uvicorn com vários workers e channel layer
em Redis.

**Project Type**: app Django `apps.game`, camada de transporte websocket.

**Performance Goals**: uma jogada é uma leitura e uma escrita no Redis, uma
cópia da partida para o diff, e dois `group_send`. A partida é pequena (80
cartas); SC-008 pede menos de 1 segundo local.

**Constraints**: mypy strict sem relaxação nova; funções de 4 a 20 linhas;
arquivos abaixo de 500 linhas; nenhum `id` nu; o motor não muda; nenhum frame
para um cliente carrega mão alheia ou deck.

**Scale/Scope**: 1 pacote novo (`protocol/`, 5 módulos), 3 consumers/estado
editados (`base.py`, `match.py`, `store.py`), `player_view.py` com dois campos,
`FakeMatchStore` com versão. 6 arquivos de teste novos, 3 editados.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | O protocolo não cria regra: todo comando termina numa porta do motor, e toda recusa de regra é a do motor. O Fluxo de Partida corrigido é consumido como o motor o entrega; a §15 fica fora, como a spec registra. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | Todo campo de mensagem e de evento nomeia o espaço: `card_instance_id`, `attacker_card_instance_ids`, `user_id`, `defeated_user_id`, `match_id`. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | `ClientCommand` é união fechada, despachada com `match` e `assert_never`. Frames e eventos são `TypedDict`. A fronteira JSON (`dict[str, object]`) é estreitada por funções de validação que devolvem tipos concretos, sem `cast` fora do parser. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | Um módulo por pergunta: forma da mensagem, código da recusa, aplicação do comando, diferença de estado, frame por destinatário. O consumer só costura. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | `FakeMatchStore` ganha versão; nenhum stub inline. O `protocol/` é puro e testado sem socket. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova. |
| Injeção de dependência | ✅ PASS | `MatchConsumer` recebe `matches`, `catalog` e `randomness` por `as_asgi(**initkwargs)`, como o `MatchmakingConsumer` já faz. |
| Logging estruturado | ✅ PASS | Falha inesperada é registrada como JSON com `match_id`, `user_id` e o `type` da mensagem, e o cliente recebe só o código genérico. |
| Portas de qualidade | ✅ PASS | pytest, mypy e black sem configuração nova. |

**Resultado**: PASS. Re-verificado depois da Fase 1: o desenho não acrescentou
dependência, relaxação nem porta no motor. **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/009-match-protocol/
├── plan.md
├── research.md          # D1–D12
├── data-model.md        # comandos, frames, eventos, recusas
├── quickstart.md
├── contracts/
│   ├── client_messages.md   # o que o cliente manda
│   ├── server_frames.md     # match_start, match_update, message_refused, eventos
│   └── refusal_codes.md     # o catálogo de códigos
└── tasks.md
```

### Source Code

```text
server/apps/game/
├── protocol/                    # NOVO: transporte puro, sem I/O
│   ├── __init__.py
│   ├── client_messages.py       # JSON cru -> ClientCommand, ou MalformedMessageError
│   ├── commands.py              # MulliganCommand, ForfeitCommand, ClientCommand, apply_command
│   ├── refusal_codes.py         # exceção -> código estável
│   ├── match_events.py          # before/after -> eventos recortados por destinatário
│   └── match_frames.py          # MatchStartPayload, MatchUpdatePayload, montagem
├── consumers/
│   ├── base.py                  # EDITADO: JSON inválido e tipo desconhecido viram recusa
│   └── match.py                 # EDITADO: recebe, aplica, grava, distribui
├── match/
│   ├── store.py                 # EDITADO: StoredMatch, get_stored, versão devolvida
│   └── player_view.py           # EDITADO: mulligan_taken nos dois lados
└── tests/
    ├── fake_match_store.py      # EDITADO: versão
    ├── test_client_messages.py  # NOVO
    ├── test_refusal_codes.py    # NOVO
    ├── test_match_commands.py   # NOVO
    ├── test_match_events.py     # NOVO
    ├── test_match_frames.py     # NOVO
    ├── test_match_consumer_play.py  # NOVO: pelo socket
    ├── test_base_consumer_lifecycle.py  # EDITADO
    ├── test_match_consumer_state.py     # EDITADO: payload com versão
    └── test_match_store.py      # EDITADO: StoredMatch
```

**Structure Decision**: `protocol/` separado de `consumers/` porque o que mora
lá não toca Channels nem Redis e é testável sem socket. É o mesmo corte que
`match/` (estado) e `engine/` (regra) já fazem.

## Complexity Tracking

Nenhuma violação a justificar.
