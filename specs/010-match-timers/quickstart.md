# Quickstart: Relógio da vez, e a correção do SACRIFICIAL FIRE

**Feature**: 010-match-timers

## Portas

```bash
cd server && pytest && mypy && black --check .
docker compose run --rm --no-deps anathema_server sh -c "cd /server && pytest"
```

A segunda linha roda os testes que precisam do Redis (`test_match_store.py`,
`test_match_wake_queue.py`).

## Os testes desta feature

| Arquivo | O que prova |
|---|---|
| `test_sacrificial_fire.py` | FIRE sem alvo dá +3 a toda a zona; unidade mandada depois não ganha; com alvo é `spell_takes_no_target`; Nexus 1 continua 1 |
| `test_spell_effect.py`, `test_spell_effects.py`, `test_mvp_catalog.py`, `test_spell_state_round_trip.py`, `test_full_match.py` | as expectativas de alvo único trocadas pela regra da §14 |
| `test_wall_clock.py` | `SystemWallClock` em milissegundos; `FakeWallClock` conforme o `Protocol` |
| `test_match_clock.py` | `clock_wake_at` em cada estado; ida e volta do documento |
| `test_turn_clock.py` | vez nova ao trocar de dono e ao virar a rodada com o mesmo dono; vez igual em feitiço, declarar, puxar o último, bloquear; relógio parado no fim |
| `test_clock_events.py` | o que venceu em cada instante; ação automática por fase; guarda recusando vez velha, prazo não vencido e aviso já mandado |
| `test_match_changes.py` | `PlayerChange`, `ClockChange` e `TurnWarningMark`: o antes guardado, a vez nova, e a recusa que não grava |
| `test_match_wake_queue.py` | Redis: índice gravado no mesmo script do estado; claim com lease; release respeitando reagendamento; 100 corridas entre passe e estouro; TTL não renovado pelo ticker |
| `test_match_clock_ticker.py` | aviso só ao dono e uma vez só; estouro nas três fases; cascata numa atualização; fim de partida por estouro |
| `test_match_clock_resilience.py` | dono desconectado; worker que morre depois do claim; dois tickers no mesmo despertar; jogada e estouro disputando; mulligan vencido de um e dos dois; desistência e partida expirada |
| `test_match_timers_lifespan.py` | startup liga o ticker, shutdown cancela e espera |
| `test_engine_reads_no_time.py` | nenhum módulo do motor importa tempo nem lê `clock` |
| `test_match_consumer_clock.py` | pelo socket: `clock` no `match_start` e no `match_update`; reconexão aos 40 s vê 5 s; feitiço aos 25 s não devolve tempo; mulligan com o próprio prazo |
| `test_matchmaking_clock.py` | a partida nasce com o prazo do mulligan e já entra no índice |
| `test_match_frames.py`, `test_match_events.py` | `ClockView` por destinatário; eventos de origem só em mudança do relógio |

Todo cenário de relógio usa `FakeWallClock` e chama `ticker.tick(now)`
diretamente: nenhum teste dorme.

## Na mão, com dois clientes

Pré-requisito: o servidor sobe com `--lifespan on` (o compose já passa).

1. Dois usuários pareiam e abrem `ws/match/?matchId=...`. O `match_start` traz
   `clock.mulligan_remaining_ms` perto de 30000 e `clock.turn: null`.
2. A responde o mulligan; B não responde. Uns 30 s depois da criação, os dois
   recebem `match_update` com `mulligan_timed_out` para B, seguido de
   `mulligan_taken` com `swapped_count: 0`, e a partida na Rodada 1 com
   `clock.turn.turn_number: 1`.
3. Ninguém joga. Aos 30 s da vez, só os sockets do dono recebem `turn_warning`.
   Aos 45 s, os dois recebem `match_update` com `turn_timed_out` e `passed`, e
   `clock.turn.turn_number: 2` com `remaining_ms` perto de 45000.
4. O dono da vez lança um feitiço aos 20 s: o `match_update` traz o mesmo
   `turn_number` e `remaining_ms` perto de 25000.
5. O dono da vez fecha o socket. O outro recebe o estouro mesmo assim.
6. Com a declaração aberta e duas unidades na zona, o atacante manda
   `cast_spell` do FIRE sem alvo: a `view` mostra +3 nas duas; mandar uma
   terceira unidade não mostra +3 nela. O mesmo `cast_spell` com
   `target_card_instance_id` recebe `spell_takes_no_target`.
7. Desistir: o `match_update` traz `clock.turn: null`, e nenhum
   `turn_warning` ou `turn_timed_out` chega depois.
8. Com os dois sockets fechados, `redis-cli -n 3 TTL match:<match_id>` continua
   diminuindo entre um estouro e outro.
