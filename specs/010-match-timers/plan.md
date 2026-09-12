# Implementation Plan: Relógio da vez, e a correção do SACRIFICIAL FIRE

**Branch**: `010-match-timers` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-match-timers/spec.md`

## Summary

Duas partes independentes.

**Parte 1 — SACRIFICIAL FIRE sem alvo** (D1). O efeito passa a declarar
`TargetKind.NONE`, e `TargetKind.ALLIED_ATTACKER` sai do conjunto. O despacho
de `spell_effect` dá o bônus a toda unidade em `combat.attacker_card_instance_ids`
no instante do lançamento, e só depois cobra o Nexus. A recusa de alvo a mais
já existe (`spell_takes_no_target`). A descrição do catálogo e sete arquivos de
teste mudam junto.

**Parte 2 — relógio da vez.** O motor não muda. Seis decisões carregam a parte.

**O estado do relógio mora no documento da partida** (D3). `Match.clock` guarda
a vez atual — número, dono, rodada, instante do aviso, instante do estouro,
aviso já mandado — e o prazo do mulligan. Nenhum módulo do motor o lê. Ficar no
documento dá atomicidade com o compare-and-swap de graça, e a reconexão o lê
pelo `get_stored` que já existe.

**A vez nova é derivada do estado depois da mudança** (D4). Toda mutação —
jogada do socket ou estouro — termina com `advance_match_clock(match, now)`:
se a partida espera um jogador e o par `(dono, rodada)` mudou, abre vez nova
com número seguinte. Feitiço, mandar e puxar atacante e bloquear não mudam o
par, então não reiniciam nada — sem nenhuma lista de ações que "não contam".

**Um índice de despertar gravado no mesmo script da gravação** (D5). Um sorted
set no Redis, membro `match_id`, score = o próximo instante de relógio da
partida. Os scripts Lua de `save` e `mutate` atualizam o índice na mesma
operação atômica que grava o estado. Não existe partida gravada sem o
despertar dela.

**Um ticker por worker, ligado pelo lifespan do ASGI** (D7, D8). Cada worker do
uvicorn roda um laço que, a cada 500 ms, reivindica os despertares vencidos com
um lease curto e os processa. Worker que cai no meio deixa o lease vencer, e
outro worker pega. O uvicorn passa a `--lifespan on`, e o `ProtocolTypeRouter`
ganha a chave `lifespan`.

**A guarda do estouro roda dentro da mutação** (D9). O estouro carrega o número
da vez que o armou. Dentro do `mutate`, sobre a leitura fresca de cada
tentativa, ele confere que a vez ainda é aquela e que o prazo venceu; se não, levanta
`ClockEventNotDueError` e nada é gravado. É isso que resolve a corrida com a
jogada real e o estouro atrasado com o mesmo mecanismo.

**Estouro não renova a expiração** (D6). `mutate` ganha `renews_expiry`; o
script de swap só chama `EXPIRE` quando ele é verdadeiro. Uma partida em que
ninguém joga some 6h depois da última jogada real.

O cliente recebe `clock` ao lado da `view` em `match_start` e `match_update`,
com o tempo restante medido pelo servidor (D12); o frame novo `turn_warning` só
para o dono da vez; e os eventos `turn_timed_out` e `mulligan_timed_out` antes
da jogada automática (D13).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Django Channels 4.3 (consumer, channel layer,
`ProtocolTypeRouter`), channels_redis 4.3, redis-py async, uvicorn 0.52.
Nenhuma dependência nova.

**Storage**: Redis, DB 3, pelo `MatchStore`. O documento da partida ganha
`clock`. A chave nova `match:wake` é um sorted set mantido pelos scripts Lua
de `save` e `mutate`. `mutate` ganha `renews_expiry`. Partidas vivas gravadas
antes do deploy não têm `clock` e não são lidas — não há produção, e o TTL as
limpa em 6h.

**Testing**: pytest 9.1 + pytest-asyncio, `cd server && pytest`. O tempo chega
por `WallClock`, e os testes usam `FakeWallClock`. O ticker é testado por
`tick(now)`, sem laço nem `sleep`, sobre `FakeMatchStore`,
`FakeMatchWakeQueue` e o `InMemoryChannelLayer` do `conftest.py`. Os scripts
Lua (índice, lease, TTL) são testados contra Redis, como `test_match_store.py`
já é.

**Target Platform**: servidor Linux, uvicorn com `--workers 4` e
`--lifespan on`, channel layer e partidas no Redis.

**Project Type**: app Django `apps.game`, camada de transporte websocket.

**Performance Goals**: aviso entre 30 e 32 s e estouro entre 45 e 47 s (SC-002)
com um laço de 500 ms. Cada worker faz uma `ZRANGEBYSCORE` a cada volta; um
estouro é uma leitura, uma escrita e dois `group_send`.

**Constraints**: mypy strict sem relaxação nova; funções de 4 a 20 linhas;
arquivos abaixo de 500 linhas; nenhum `id` nu; nenhum módulo de
`apps/game/engine/` importa tempo nem lê `Match.clock`; sem trava com tempo de
vida (o lease do índice não protege estado — só evita trabalho repetido; quem
protege o estado é o compare-and-swap); os relógios dos hosts são sincronizados
por NTP.

**Scale/Scope**: Parte 1 — 3 módulos editados e 7 testes ajustados. Parte 2 —
1 pacote novo (`match_timers/`, 2 módulos), 6 módulos novos em pacotes
existentes, 11 editados, 2 arquivos de deploy editados, 3 fakes novos ou
editados, 9 arquivos de teste novos e 4 editados.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | A Parte 1 corrige o código para a §14. A Parte 2 aplica a §15 e as constantes da §12 sem regra nova: o estouro é uma ação comum pela porta do motor, e a partida abandonada expira sem derrota, como o mantenedor decidiu. A leitura de "mora no consumer" como "mora no transporte" está registrada na spec. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | `turn_number`, `holder_user_id`, `match_id`, `user_id`. O membro do índice é o `match_id`. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | `EpochMillis` é `NewType` de `int`. O evento de relógio vencido é união fechada (`TurnExpiry \| TurnWarning \| MulliganExpiry`) despachada com `match` e `assert_never`. Frames e documento são `TypedDict`. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | Um módulo por pergunta: que horas são (`wall_clock`), o que o relógio guarda (`match_clock`), quando começa vez nova (`turn_clock`), o que venceu e qual ação aplica (`clock_events`), a mutação com o antes guardado (`match_changes`), a entrega aos grupos (`match_delivery`), a fila de despertar (`wake_queue`), o laço (`ticker`), o ciclo de vida (`lifespan`). O `consumers/match.py` encolhe. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | `FakeWallClock`, `FakeMatchWakeQueue` e `FakeMatchStore` com índice e expiração. A corrida usa `InterleavedMatchStore`, subclasse nomeada, como o `AlwaysStaleMatchStore` que já existe. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova. `--lifespan on` é flag do uvicorn fixado. |
| Injeção de dependência | ✅ PASS | `WallClock` chega por `as_asgi(clock=...)` nos dois consumers e pelo construtor do ticker. O único ponto que lê `get_match_store()` e `get_channel_layer()` para o ticker é a fábrica de composição de `core/asgi.py`. |
| Wrapper de terceiros | ✅ PASS | O sorted set fica atrás de `MatchWakeQueue`, no formato de `MatchStore`. O tempo do sistema, atrás de `WallClock`, no formato de `RandomSource`. |
| Logging estruturado | ✅ PASS | Estouro aplicado, estouro recusado pelo motor e falha do ticker saem em JSON com `match_id`, `turn_number` e a espécie do evento. |
| Portas de qualidade | ✅ PASS | pytest, mypy e black sem configuração nova. |

**Resultado**: PASS. Re-verificado depois da Fase 1: nenhuma relaxação, nenhuma
dependência, e nenhuma porta do motor recebe tempo — `test_engine_reads_no_time.py`
transforma isso em teste. **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/010-match-timers/
├── plan.md
├── research.md          # D1–D17
├── data-model.md        # relógio no documento, índice de despertar, frames, eventos
├── quickstart.md
├── contracts/
│   ├── server_frames.md     # clock em match_start/match_update, turn_warning, eventos novos
│   └── client_messages.md   # SACRIFICIAL FIRE sem alvo
└── tasks.md
```

### Source Code

```text
server/
├── core/
│   └── asgi.py                          # EDITADO: chave "lifespan" no ProtocolTypeRouter
└── apps/game/
    ├── wall_clock.py                    # NOVO: EpochMillis, WallClock, SystemWallClock
    ├── cards/
    │   ├── effects.py                   # EDITADO (P1): FIRE com TargetKind.NONE; ALLIED_ATTACKER sai
    │   └── mvp_catalog.py               # EDITADO (P1): descrição do FIRE
    ├── engine/
    │   ├── spell_cast_guards.py         # EDITADO (P1): some a guarda de atacante
    │   └── spell_effect.py              # EDITADO (P1): bônus em toda a zona de ataque
    ├── match/
    │   ├── match_clock.py               # NOVO: TurnDeadline, MatchClock, clock_wake_at
    │   ├── match_state.py               # EDITADO: campo clock
    │   ├── documents.py                 # EDITADO: MatchClockDocument
    │   ├── serialization.py             # EDITADO: ida e volta do clock
    │   ├── store.py                     # EDITADO: índice nos scripts; renews_expiry
    │   ├── client.py                    # EDITADO: fila de despertar do processo; docstring sem --lifespan off
    │   └── wake_queue.py                # NOVO: MatchWakeQueue, claim com lease e release
    ├── protocol/
    │   ├── turn_clock.py                # NOVO: constantes §12, opening_match_clock, advance_match_clock
    │   ├── clock_events.py              # NOVO: due_clock_event, automatic_command, guardas
    │   ├── match_changes.py             # NOVO: PlayerChange e ClockChange (o RecordedChange sai do consumer)
    │   ├── match_frames.py              # EDITADO: ClockView nos payloads; TurnWarningPayload
    │   ├── match_events.py              # EDITADO: turn_timed_out, mulligan_timed_out
    │   └── __init__.py                  # EDITADO: exports
    ├── consumers/
    │   ├── match.py                     # EDITADO: WallClock injetado; entrega extraída; handler do aviso
    │   ├── match_delivery.py            # NOVO: update e aviso aos grupos de usuário
    │   └── matchmaking.py               # EDITADO: prazo do mulligan na criação
    ├── match_timers/                    # NOVO
    │   ├── __init__.py
    │   ├── ports.py                     # TickerMatchStore e TickerWakeQueue (Protocol)
    │   ├── ticker.py                    # MatchClockTicker: tick(now) e run()
    │   └── lifespan.py                  # app ASGI que liga e desliga o ticker
    └── tests/
        ├── fake_wall_clock.py           # NOVO
        ├── fake_match_wake_queue.py     # NOVO
        ├── interleaved_match_store.py   # NOVO: jogada concorrente entre leitura e gravação
        ├── engine_sources.py            # NOVO: extraído de test_full_match.py
        ├── clock_boards.py              # NOVO: tabuleiros e sockets que os testes de relógio repetem
        ├── test_match_changes.py        # NOVO: PlayerChange, ClockChange, TurnWarningMark
        ├── test_match_clock_resilience.py  # NOVO: desconexão, workers, corridas, abandono
        ├── test_matchmaking_clock.py    # NOVO: o prazo do mulligan nasce com a partida
        ├── fake_match_store.py          # EDITADO: compare-and-swap com gancho, índice de despertar e expiração
        ├── test_sacrificial_fire.py     # EDITADO (P1)
        ├── test_spell_effect.py         # EDITADO (P1)
        ├── test_spell_effects.py        # EDITADO (P1)
        ├── test_mvp_catalog.py          # EDITADO (P1)
        ├── fake_spell_board.py          # EDITADO (P1)
        ├── test_full_match.py           # EDITADO (P1)
        ├── test_spell_state_round_trip.py  # EDITADO (P1)
        ├── test_wall_clock.py           # NOVO
        ├── test_match_clock.py          # NOVO: wake_at, ida e volta
        ├── test_turn_clock.py           # NOVO: vez nova e vez igual, transição a transição
        ├── test_clock_events.py         # NOVO: o que venceu, ação por fase, guardas
        ├── test_match_wake_queue.py     # NOVO: Redis — claim, lease, release, índice atômico
        ├── test_match_clock_ticker.py   # NOVO: estouros, aviso, mulligan, desconectado, corrida
        ├── test_match_timers_lifespan.py  # NOVO: startup liga, shutdown cancela
        ├── test_engine_reads_no_time.py # NOVO: nenhum módulo do motor importa tempo
        ├── test_match_consumer_clock.py # NOVO: pelo socket — clock na visão, reconexão, relógio não reinicia
        ├── test_match_store.py          # EDITADO: TTL não renovado; índice gravado junto
        ├── test_match_frames.py         # EDITADO: clock no payload
        └── test_match_events.py         # EDITADO: eventos de origem
dockerfile                               # EDITADO: --lifespan on
docker-compose.yml                       # EDITADO: --lifespan on
```

**Structure Decision**: o que é puro fica em `protocol/` (vez nova, o que
venceu, qual ação), ao lado dos comandos que já moram lá. O que toca Redis fica
em `match/`, ao lado do `MatchStore`. O laço e o ciclo de vida ganham
`match_timers/` porque não são consumer — não têm socket — e não são protocolo
— fazem I/O. É o mesmo corte que `match/`, `engine/` e `protocol/` já fazem.

## Complexity Tracking

Nenhuma violação a justificar.
