# Quickstart: Protocolo de partida

**Feature**: 009-match-protocol

## Portas

```bash
cd server && pytest && mypy && black --check .
docker compose run --rm --no-deps anathema_server sh -c "cd /server && pytest"
```

A segunda linha roda os testes que precisam do Redis (`test_match_store.py`).

## Os testes desta feature

| Arquivo | O que prova |
|---|---|
| `test_client_messages.py` | forma de cada mensagem, autor vindo do socket, recusas de forma |
| `test_refusal_codes.py` | toda recusa do motor tem código, e nenhum se repete |
| `test_match_commands.py` | mulligan que fecha o setup já entra na Rodada 1; desistência; ações |
| `test_match_events.py` | a jogada e as consequências, recortadas por destinatário |
| `test_match_frames.py` | frame por destinatário sem mão alheia nem deck |
| `test_match_consumer_play.py` | pelo socket: mulligan e Rodada 1 sozinha, jogadas aos dois, combate passo a passo, desistência, recusas só a quem mandou com o socket aberto |
| `test_match_consumer_flow.py` | pelo socket: carta da mão alheia recusada como inexistente, reconexão em cada ponto, dois sockets do mesmo jogador, versão crescente, partida expirada, e a partida inteira com varredura de cartas escondidas |
| `test_base_consumer_lifecycle.py` | frame binário, JSON inválido, `type` ausente e desconhecido recusados em todo socket |
| `test_match_store.py` | versão devolvida e lida junto do estado; dois workers fechando o setup ao mesmo tempo |

## Na mão, com dois clientes

1. Dois usuários entram na fila (`ws/matchmaking/`) e recebem `match_found`.
2. Cada um abre `ws/match/?matchId=...` e recebe `match_start` com `version` e
   `view`; `view.you.mulligan_taken` é `false`.
3. A manda `{"type": "mulligan", "payload": {"card_instance_ids": []}}`. Os dois
   recebem `match_update`; B vê `view.opponent.mulligan_taken == true` e um
   evento `mulligan_taken` com `swapped_count: 0`.
4. B manda o mulligan. Os dois recebem `match_update` com `view.phase ==
   "action"`, `round_number == 1` e energia 1, sem mensagem extra.
5. Quem tem a vez manda `{"type": "pass"}`; o outro também. A atualização chega
   já na rodada 2, com `round_started` e `cards_drawn`.
6. Mandar `{"type": "banana"}`: só aquele socket recebe `message_refused` com
   `unknown_message_type`, e o socket segue aberto.
7. Mandar `{"type": "forfeit"}`: os dois recebem `match_update` com
   `view.outcome.reason == "forfeit"`; qualquer jogada seguinte recebe
   `match_is_over`.
