# Implementation Plan: Resultado de partida, registrado uma vez só

**Branch**: `012-match-result-history` | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-match-result-history/spec.md`

## Summary

A partida que termina deixa de morrer com o TTL de 6 horas do Redis: vira uma
linha no banco ligada aos dois perfis, e as estatísticas dos dois — zeradas desde
o cadastro — sobem na mesma transação. O jogador consulta depois o próprio
histórico, paginado.

O requisito que carrega a feature é o **exatamente uma vez**, e ele é resolvido
por três decisões que se reforçam:

1. **Só a transição registra.** Uma função pura sobre o par (antes, depois)
   devolve o registro a gravar, ou `None`. Toda observação de partida já terminada
   devolve `None` — não existe leitura a partir da qual registrar.
2. **Fora da mutação.** A gravação acontece depois do `mutate` bem-sucedido, nos
   dois únicos pontos que podem terminar uma partida. Dentro de `mutate` seria
   reaplicada pela retentativa do compare-and-swap, que é rotina.
3. **`match_id` único no banco.** Entre a gravação do estado e a do banco existe
   uma janela; a unicidade é o que faz a corrida perder em vez de duplicar. O
   registro e os dois incrementos de estatística ficam na mesma transação.

Duas mudanças sustentam o resto: o **instante de criação** passa a fazer parte do
estado da partida (estado de transporte, como o relógio da §15 já é), e o **deck
da partida** — lista congelada da entrada na fila, mais o nome que ele tinha —
viaja junto para dentro do registro.

O motor não é tocado. O protocolo, o relógio e o compare-and-swap não mudam de
contrato.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Django 5.2 LTS, Django REST Framework 3.18,
Django Channels 4.3, `redis.asyncio`, Simple JWT 5.5.1

**Storage**: PostgreSQL/SQLite via ORM do Django para o registro permanente;
Redis 8.6 para o estado vivo da partida (TTL de 6 horas, inalterado)

**Testing**: pytest 9.1 + pytest-django 4.14 + pytest-asyncio 1.4, comando único
`cd server && pytest`

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`), Uvicorn
com múltiplos workers

**Project Type**: web service — backend HTTP + websocket, sem cliente neste repo

**Performance Goals**: o registro acontece depois da entrega do frame final, então
não entra no caminho quente da jogada. A listagem do histórico serve 20 linhas com
dois índices compostos e um `select_related` de dois perfis.

**Constraints**: nenhuma escrita de banco dentro de `MatchStore.mutate`; nenhum
teste de websocket pode tocar o banco (`apps/game/tests/conftest.py`); o motor não
lê tempo nem conhece banco (`test_engine_reads_no_time.py`); mypy `strict` com
`warn_unreachable` verde.

**Scale/Scope**: uma linha por partida terminada, duas por jogador consultadas por
página. Um modelo novo, uma rota nova, dois campos novos no estado da partida,
duas linhas novas nos dois caminhos de escrita existentes.

## Constitution Check

*GATE: passa antes da Phase 0 e re-verificado depois da Phase 1.*

| Princípio | Como esta feature cumpre |
|---|---|
| **I. Notas de decisão são a fonte da verdade** | Nada de domínio é redecidido: as duas saídas da §10 e a ausência de empate vêm do motor. A decisão 0001 (um perfil por usuário, `profile.pk == user.id`) é o que permite a FK ser a própria identidade, sem coluna espelho. Nenhuma nota nova é escrita — o pedido não pediu. |
| **II. Identidade nomeada, nunca `id` pelado** | O contrato HTTP expõe `match_id`, `user_id`. Nenhum campo `id`. As FKs `winner`/`loser` viram `opponent: {user_id: ...}` no serializer. |
| **III. Tipos explícitos, mypy strict** | `ChosenDeck`, `FinishedSide` e `FinishedMatch` são dataclasses congeladas e anotadas. Os campos novos do documento entram por `TypedDict(total=False)`, que é o que faz `.get()` valer `T \| None` sem `cast`. O único `# type: ignore` novo é o de `database_sync_to_async`, com o comentário que os outros dois já carregam. |
| **IV. Unidades pequenas, uma responsabilidade** | Módulos separados por responsabilidade: derivar o resultado (`finished_match.py`), gravá-lo (`recorder.py`), disparar a gravação (`record_finished_match.py`), servi-lo (`match_history_view.py`). Nenhum arquivo novo passa de 120 linhas. |
| **V. Comportamento testado com fakes nomeados** | `FakeFinishedMatchRecorder` é classe nomeada, no padrão dos 12 fakes que `apps/game/tests/` já tem. Ela é o que mantém a suíte de socket fora do banco. |
| **Stack fixada** | Nenhuma dependência nova. Paginação e `ListAPIView` são do DRF já instalado. |
| **Injeção de dependência** | O gravador chega por construtor no `MatchConsumer` e no `MatchClockTicker`, como `matches`, `catalog`, `randomness` e `clock` já chegam. |
| **Biblioteca de terceiro atrás de interface própria** | `FinishedMatchRecorder` é a interface do projeto; o ORM fica do outro lado dela, invisível ao caminho de partida. |
| **Logging** | A falha de gravação vai para log estruturado, com `match_id`, pelo `logging` que o ticker e os consumers já usam. |

**Resultado**: passa. Nenhuma violação a justificar — a seção *Complexity
Tracking* fica vazia e foi removida.

**Re-verificação pós-Phase 1**: passa. O desenho não introduziu god file, não
duplicou lógica (a condição de transição é uma linha, e o tipo do frame de
protocolo não é reusado — ver D1), e não criou segunda fonte de identidade (D5).

## Project Structure

### Documentation (this feature)

```text
specs/012-match-result-history/
├── plan.md              # Este arquivo
├── research.md          # Phase 0 — 12 decisões técnicas com alternativas rejeitadas
├── data-model.md        # Phase 1 — as três camadas de dado
├── quickstart.md        # Phase 1 — como provar que funciona
├── contracts/
│   ├── http_match_history.md          # GET /game/matches/
│   └── finished_match_recorder.md     # a porta de gravação
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
server/apps/game/
├── history/                              # NOVO — o registro do resultado
│   ├── __init__.py
│   ├── finished_match.py                 # FinishedMatch, FinishedSide, finished_match()
│   ├── recorder.py                       # FinishedMatchRecorder + DatabaseFinishedMatchRecorder
│   └── record_finished_match.py          # o disparo, que nunca levanta
├── models/                               # NOVO — substitui o models.py vazio
│   ├── __init__.py
│   └── match_record.py                   # MatchRecord
├── migrations/
│   └── 0001_initial.py                   # NOVO — o app não tem nenhuma hoje
├── match_history_view.py                 # NOVO — ListAPIView + paginação própria
├── match_history_serializers.py          # NOVO — a linha do histórico
├── match/
│   ├── chosen_deck.py                    # NOVO — ChosenDeck
│   ├── match_state.py                    # + Match.started_at
│   ├── player_state.py                   # + PlayerState.chosen_deck
│   ├── documents.py                      # + campos opcionais (TypedDict total=False)
│   ├── serialization.py                  # ida e volta dos dois campos novos
│   └── __init__.py                       # reexporta ChosenDeck
├── matchmaking/
│   └── queue.py                          # QueueEntry ganha deck_name; hash guarda objeto
├── engine/
│   └── match_setup.py                    # MatchEntry ganha deck_name; monta chosen_deck
├── consumers/
│   ├── matchmaking.py                    # escreve started_at; leva o nome do deck
│   └── match.py                          # + uma linha: record_finished_match
├── match_timers/
│   └── ticker.py                         # + uma linha em _expire
├── urls.py                               # + path("matches/", ...)
└── tests/
    ├── fake_finished_match_recorder.py   # NOVO
    ├── test_finished_match.py            # NOVO — a derivação pura
    ├── test_finished_match_record.py     # NOVO — gravação, estatísticas, falhas
    ├── test_finished_match_once.py       # NOVO — corrida, reconexão, abandono
    └── test_match_history_api.py         # NOVO — o contrato HTTP

server/apps/players/
├── services/deck_queries.py              # PlayerDeckSource devolve ChosenDeck
└── (models/player.py inalterado — PlayerStats passa a ser escrito, não muda)
```

**Structure Decision**: o app `game` recebe o modelo, o serviço e a rota. O
registro é de partida, o `MatchEndReason` que vira `choices` é de `game`, e o app
não tem migração nenhuma hoje — a primeira nasce limpa. `players` só muda na porta
de leitura de deck, que passa a devolver o nome junto da lista.

`apps/game/models.py` (vazio, com o comentário de scaffold do Django) vira o
pacote `apps/game/models/`, no mesmo formato que `apps/players/models/` já usa —
inclusive o `__all__` explícito que `no_implicit_reexport` exige.

## Phase 0 — Research

Concluída. Doze decisões em [research.md](research.md), cada uma com alternativas
rejeitadas:

| # | Decisão |
|---|---|
| D1 | Transição detectada por função pura, sem reusar o tipo do frame de protocolo |
| D2 | Disparo nos dois pontos que já chamam `mutate`, depois da entrega |
| D3 | `match_id` único + savepoint em torno do INSERT |
| D4 | Estatísticas com `F()`, sem perder incremento concorrente |
| D5 | `SET_NULL` nas duas FKs, sem coluna espelho de `user_id` |
| D6 | Deck da partida em quatro colunas simétricas, listas em `JSONField` |
| D7 | `started_at` como estado de transporte, escrito fora do motor |
| D8 | Campos novos opcionais no documento, para as partidas vivas da implantação |
| D9 | Porta `Protocol` injetada, para a suíte de socket seguir fora do banco |
| D10 | `GET /game/matches/`, `ListAPIView` com paginação local |
| D11 | Isolamento pelo queryset, sem rota parametrizada por jogador |
| D12 | `play_time` e `duration_seconds` em segundos inteiros |

Nenhum `NEEDS CLARIFICATION` restante.

## Phase 1 — Design & Contracts

Concluída.

- [data-model.md](data-model.md) — as três camadas: estado da partida (dois campos
  novos), o valor que a transição produz (puro, sem ORM), e o registro no banco
  (uma tabela, dois índices compostos).
- [contracts/http_match_history.md](contracts/http_match_history.md) — a rota, os
  parâmetros, o corpo, as três recusas.
- [contracts/finished_match_recorder.md](contracts/finished_match_recorder.md) — a
  porta de gravação, suas quatro garantias, quem injeta e quem dispara.
- [quickstart.md](quickstart.md) — oito cenários de validação, mapeados aos
  critérios de sucesso da spec.
- Contexto do agente atualizado: os marcadores `SPECKIT` do `CLAUDE.md` apontam
  para este plano.

### Ordem de implementação sugerida

Quatro fatias, cada uma verde antes da seguinte:

1. **O estado carrega o começo e o deck** — `ChosenDeck`, `Match.started_at`,
   `PlayerState.chosen_deck`, documento e serialização, o nome do deck atravessando
   fila e `MatchEntry`. Prova: ida e volta pelo Redis preserva os dois campos, e
   `test_queued_deck_is_frozen.py` continua verde.
2. **A derivação** — `FinishedMatch` e `finished_match()`. Puro, sem banco. Prova:
   transição devolve o registro; observação devolve `None`.
3. **A gravação** — `MatchRecord`, migração, `DatabaseFinishedMatchRecorder`,
   `record_finished_match`, as duas linhas nos dois caminhos de escrita, o fake.
   Prova: exatamente uma vez sob corrida, estatísticas na mesma transação, falha
   que não derruba a partida.
4. **A consulta** — serializer, view, rota. Prova: o contrato HTTP inteiro.

A fatia 1 é a única que toca código de partida existente em mais de um arquivo; é
onde o risco de regressão mora, e por isso vem primeiro e sozinha.
