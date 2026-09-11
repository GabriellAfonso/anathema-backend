---

description: "Task list for 009-match-protocol"
---

# Tasks: Protocolo de partida

**Input**: Design documents from `specs/009-match-protocol/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: obrigatórios (princípio V da constituição).

**Organization**: a fundação é grande de propósito — as sete histórias da spec
são o mesmo caminho (mensagem → comando → mutação → frame por destinatário)
visto de ângulos diferentes. Com a fundação pronta, cada história é um conjunto
de testes pelo socket que prova um ângulo, e o ajuste que o teste exigir.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Rodar `cd server && pytest && mypy && black --check .` e confirmar a base verde (os 29 testes de Redis rodam no container: `docker compose run --rm --no-deps anathema_server sh -c "cd /server && pytest"`)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T002 Versão de escrita em `server/apps/game/match/store.py` ([research.md D7](./research.md#d7-versão-de-escrita-como-posição)): `StoredMatch(match, version)`; `SAVE_SCRIPT` e `SWAP_SCRIPT` devolvem a versão nova (swap devolve 0 quando recusa); `save` passa a devolver a versão; `get_stored(match_id) -> StoredMatch | None`; `mutate` devolve `StoredMatch`. Ajustar `server/apps/game/tests/test_match_store.py` aos retornos novos e acrescentar testes de `get_stored` e da versão devolvida
- [X] T003 [P] `server/apps/game/tests/fake_match_store.py`: guardar `(match, version)`, com `get_stored` e `mutate` devolvendo `StoredMatch` e a versão crescendo a cada escrita
- [X] T004 [P] `server/apps/game/protocol/refusal_codes.py` e `server/apps/game/protocol/__init__.py`: `Refusal(code, message)`, os códigos do protocolo, o dicionário por tipo exato das recusas do motor e de `MulliganAlreadyTakenError` ([contracts/refusal_codes.md](./contracts/refusal_codes.md)), `refusal_for(error) -> Refusal | None`. Testes em `server/apps/game/tests/test_refusal_codes.py`: toda subclasse de `IllegalActionError` tem código, códigos únicos, `MatchIsOverError` ≠ `PhaseForbidsActionError`
- [X] T005 [P] `server/apps/game/protocol/client_messages.py`: `MalformedMessageError`, `parse_client_message(content, *, author_user_id) -> ClientCommand` para os onze tipos de [contracts/client_messages.md](./contracts/client_messages.md). Testes em `server/apps/game/tests/test_client_messages.py`: cada tipo bem formado, autor do socket mesmo com `actor_user_id`/`user_id` no payload, campo faltando, texto/booleano/fracionário/nulo/zero como identificador, payload não-objeto, `type` desconhecido, `type` ausente, alvo opcional ausente e nulo
- [X] T006 [P] `server/apps/game/protocol/commands.py`: `MulliganCommand`, `ForfeitCommand`, `ClientCommand`, `apply_command(match, command, *, catalog, randomness)` ([research.md D4](./research.md#d4-comandos-e-a-aplicação-deles)). Testes em `server/apps/game/tests/test_match_commands.py`: primeiro mulligan deixa a partida em `MULLIGAN`; o segundo a leva a `ACTION` na rodada 1 com energia 1; desistência; uma ação vai ao motor; recusa do motor atravessa
- [X] T007 [P] `server/apps/game/protocol/match_events.py`: `MatchEvent` (TypedDicts com `kind`) e `describe_change(before, after, command, *, recipient_user_id) -> list[MatchEvent]` ([research.md D5](./research.md#d5-eventos-pela-diferença-de-estado)). Testes em `server/apps/game/tests/test_match_events.py`: cada jogada; dano, morte, Nexus, rodada nova, compras (cartas para o próprio, só contagem para o oponente), mulligan só com contagem, fim da partida com motivo, ordem fixa
- [X] T008 `server/apps/game/match/player_view.py`: `mulligan_taken` em `PlayerSideView` e `OpponentSideView`; `server/apps/game/protocol/match_frames.py`: `MatchStartPayload`, `MatchUpdatePayload`, `match_start_payload(stored, user_id)`, `match_update_payload(before, stored, command, user_id)`. Testes em `server/apps/game/tests/test_match_frames.py` e `server/apps/game/tests/test_player_view.py`: campos novos, versão, eventos recortados, nenhum identificador de mão ou deck do oponente no frame serializado
- [X] T009 `server/apps/game/consumers/base.py`: `send_refusal(code, message)` (`message_refused`), `receive` que recusa frame binário e JSON inválido/não-objeto, `receive_json` que recusa `type` ausente/não-texto (`malformed_message`) e sem handler (`unknown_message_type`). Testes em `server/apps/game/tests/test_base_consumer_lifecycle.py`
- [X] T010 `server/apps/game/consumers/match.py`: `catalog` e `randomness` injetáveis; guardar só `match_id`; `match_start` com `match_start_payload` a partir de `get_stored`; `receive_json` que ignora socket recusado pelos gates, faz `parse_client_message`, aplica dentro de `mutate` guardando o antes da tentativa ([research.md D8](./research.md#d8-o-antes-da-tentativa-gravada)), distribui `match.update` ao grupo de usuário de cada jogador ([research.md D6](./research.md#d6-distribuição-pelo-grupo-de-usuário)), e traduz falhas em recusa ([research.md D10](./research.md#d10-falhas-do-protocolo)); handler `match_update` que confere `match_id`. Ajustar `server/apps/game/tests/test_match_consumer_state.py` e `server/apps/game/tests/test_match_consumer_access.py` ao payload `{version, view}`

**Checkpoint**: `pytest` e `mypy` verdes.

---

## Phase 3: User Story 1 - Mulligan pelo socket, e a Rodada 1 começa sozinha (P1) 🎯 MVP

- [X] T011 [US1] Em `server/apps/game/tests/test_match_consumer_play.py`: dois sockets; mulligan de A chega aos dois com `opponent.mulligan_taken` e evento de contagem; mulligan de B leva os dois à Fase de Ação da Rodada 1 sem mensagem extra; mulligan repetido e depois do setup recusados só a quem mandou com `mulligan_already_taken`; jogada durante o mulligan recusada

## Phase 4: User Story 2 - Jogar a partida (P1)

- [X] T012 [US2] Em `server/apps/game/tests/test_match_consumer_play.py`: unidade e feitiço aceitos chegam aos dois, cada um com a própria mão; autor forjado no payload é ignorado; dois passes chegam como uma atualização já na rodada seguinte; declaração, mandar, puxar de volta, **Atacar**, bloqueio e fim da janela produzem uma atualização cada; desistência fora da vez termina a partida para os dois com `reason == "forfeit"`

## Phase 5: User Story 3 - Recusa com código estável (P1)

- [X] T013 [US3] Em `server/apps/game/tests/test_match_consumer_play.py`: mensagem sem `type`, `type` desconhecido, JSON inválido, identificador em formato errado, jogada ilegal (energia) — cada uma recusada só no socket que mandou, com o código esperado, o oponente sem frame, a partida igual, e o socket aceitando uma jogada legal logo depois

## Phase 6: User Story 4 - Nenhum frame entrega o que o jogador não pode ver (P1)

- [X] T014 [US4] Em `server/apps/game/tests/test_match_consumer_play.py`: varredura dos frames recebidos por A ao longo de mulligans, compras e jogadas — nenhum identificador de instância que esteja na mão ou no deck de B no momento do frame; citar carta da mão de B dá a mesma recusa que carta inexistente

## Phase 7: User Story 5 - Reconexão (P2)

- [X] T015 [US5] Em `server/apps/game/tests/test_match_consumer_play.py`: reconectar com só o próprio mulligan enviado, só o do oponente, declaração aberta, janela do defensor aberta e partida terminada devolve a visão gravada, com `mulligan_taken` certo e a versão atual

## Phase 8: User Story 6 - Concorrência e sockets repetidos (P2)

- [X] T016 [US6] Em `server/apps/game/tests/test_match_consumer_play.py`: dois sockets do mesmo jogador recebem a atualização e a recusa vai só ao que mandou; a versão cresce a cada atualização; partida expirada recusada com `match_not_found` sem fechar o socket; jogada avaliada contra o estado gravado depois de mudanças feitas por outro socket. Em `server/apps/game/tests/test_match_store.py`: dois `MatchStore` sobre o mesmo Redis aplicando `apply_command` de mulligan ao mesmo tempo chegam à Rodada 1

## Phase 9: User Story 7 - Partida inteira pela rede (P3)

- [X] T017 [US7] Em `server/apps/game/tests/test_match_consumer_play.py`: roteiro do jogador automático de `test_full_match.py` mandado pelos dois sockets, do mulligan ao resultado; os dois recebem a partida terminada; uma jogada a mais é recusada com `match_is_over`

---

## Phase 10: Polish

- [X] T018 Rodar `cd server && pytest && mypy && black --check .` e a suíte no container com Redis
- [X] T019 [P] Conferir tamanho (≤500 linhas por arquivo, ≤20 por função nova) em `server/apps/game/protocol/` e `server/apps/game/consumers/`
- [X] T020 [P] Conferir [quickstart.md](./quickstart.md) e os três contratos contra o que foi implementado, corrigindo o documento onde divergir

## Dependencies

- T002 → T003, T010; T004–T007 em paralelo; T008 depois de T007; T009 antes de T010; T010 depois de T002–T009
- Fases 3 a 9 dependem da Fase 2 e são independentes entre si (todas em `test_match_consumer_play.py`, então sequenciais na prática)

## Registro da implementação (2026-09-11)

- Os testes pelo socket ficaram em dois arquivos, para caber no limite de 500
  linhas: `test_match_consumer_play.py` (US1, US2, US3) e
  `test_match_consumer_flow.py` (US4, US5, US6, US7), com os passos comuns em
  `tests/match_sockets.py`.
- T008: `match_start_payload` e `match_update_payload` recebem partida e versão
  separadas, e não `StoredMatch` — `protocol/` fica sem importar o módulo do
  Redis.
- T010: o socket de partida não usa o roteamento `handle_<type>` do
  `BaseConsumer`; sobrescreve `receive_json` e deixa a forma com o `protocol`.
- US7 achou um falso positivo no próprio teste: a carta que o oponente acabou
  de jogar aparece no evento dele, e deve. A varredura compara com as cartas
  escondidas **depois** da jogada, lidas só depois de as duas atualizações
  chegarem.
- Portas: 749 testes locais, 783 no container com Redis; mypy e black limpos.

