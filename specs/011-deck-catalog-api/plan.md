# Implementation Plan: Decks do jogador, e o catálogo servido ao cliente

**Branch**: `011-deck-catalog-api` | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-deck-catalog-api/spec.md`

## Summary

Duas partes. A primeira não depende da segunda; a segunda não existe sem a
primeira.

**Parte 1 — o catálogo pelo HTTP** (D5, D6). `GET game/cards/` serve as 29
cartas do `mvp_catalog()` que o motor já usa — não há segunda lista. Cada carta
leva identificador, tipo, nome, custo e imagem; unidade leva ataque e vida;
feitiço leva a descrição para o jogador e, para o cliente, os quatro campos que
`SpellEffectShape` já declara: `requires_target`, `target_kind`, `duration` e
`declaration_only`. Como os quatro estão na base comum da união de efeitos,
servi-los não exige `match` nenhum, e um efeito novo é servido certo sem tocar
no módulo. O payload é montado uma vez por processo -- o `@cache` mora na view, que é o
ponto de composição, e o catálogo em si vem de `get_card_catalog()`, um handle
por processo no formato de `match/client.py` --, porque o catálogo é congelado e
a resposta não depende de quem pergunta.

**Parte 2 — o deck do jogador.** Cinco decisões carregam a parte.

**O deck mora em `apps.players`** (D1, D2). `PlayerDeck` tem FK para
`PlayerProfile`, um `name` e `card_ids` num `JSONField` — lista, com ordem e
repetição preservadas. A direção de importação já existente (`apps.game` →
`apps.players`) é preservada, e `apps.game.cards` continua folha. A PK é
exposta como `deck_id`, nunca como `id`.

**Salvar exige deck válido** (D3). Um serviço só —
`services/deck_validation.py` — confere o nome, o teto de 20 e chama
`deck_problems()` da feature 001 como está. Nada das três regras é
reimplementado. Deck recusado não é salvo nem parcialmente: a edição deixa o
deck guardado como estava.

**O isolamento sai da consulta, não de um `if`** (D4, D11). Toda operação por
identificador parte de `filter(profile=<autenticado>, pk=deck_id)`. Deck alheio
e deck inexistente percorrem o mesmo caminho e produzem o mesmo `404`. Não
existe ramo que saiba a diferença, então não existe ramo que possa vazá-la. A
porta assíncrona que o websocket usa devolve `None` pelos dois motivos, pela
mesma razão.

**Entrar na fila vira uma mensagem, e o deck viaja com a entrada** (D8, D10,
D12). `connect` não entra mais na fila; o cliente manda `{"type":
"join_queue", "payload": {"deck_id": N}}`. O consumer confere o campo, busca o
deck do dono, valida contra o catálogo do momento e **só então** chama a fila —
nenhuma recusa depois disso, então ninguém ocupa lugar na fila com deck que
será recusado e nenhum par é consumido. A fila passa a guardar
`QueueEntry(user_id, deck)`: a lista FIFO continua com `user_id` — é o que faz
o `LREM` da reentrada funcionar — e os decks vão para um hash paralelo escrito
e lido no **mesmo script Lua**, de modo que o par continua saindo de uma
operação indivisível. O que foi validado na entrada é o que a partida usa.

**O deck inicial nasce na transação do perfil** (D13, D14).
`create_player_for_user` já é `@transaction.atomic`; ganha a criação do deck
inicial, com a lista de `starter_deck(catalog)`. O `starter_deck` deixa de ser
andaime do matchmaking e vira o conteúdo desse deck. O `deck_for` do consumer
some, e o setup da §3 passa a receber dois decks de verdade sem mudar em nada.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Django 5.2, DRF 3.18 (`APIView`, `IsAuthenticated`,
serializers), Django Channels 4.3 (consumer, `database_sync_to_async`),
redis-py async, Simple JWT 5.5.1. **Nenhuma dependência nova.**

**Storage**: SQLite pelo ORM — uma tabela nova, `players_playerdeck`, com
`card_ids` em `JSONField`; migração `0002_playerdeck.py`, só `CreateModel`,
sem dado a migrar. Redis DB 2 (matchmaking) ganha a chave `matchmaking:decks`,
um hash mantido pelos mesmos scripts Lua que mantêm a fila. Nada no Redis DB 3
(partidas) muda.

**Testing**: pytest 9.1 + pytest-asyncio, `cd server && pytest`. Testes de
banco em `apps/players/tests/` com `django_db`; testes de socket em
`apps/game/tests/` continuam **sem banco**, porque o deck chega ao consumer por
porta injetada e o teste usa `FakePlayerDeckSource`. O script Lua é testado
contra Redis de verdade, como `test_matchmaking_queue.py` já é.

**Target Platform**: servidor Linux, uvicorn com `--workers 4`, Redis 8.6.

**Project Type**: backend Django — app `apps.players` (dado do jogador, API
HTTP) e app `apps.game` (catálogo, fila, socket de matchmaking).

**Performance Goals**: catálogo montado uma vez por processo (29 cartas), então
a resposta é serialização pura. Listagem de decks é uma consulta, com teto de 20
linhas. A entrada na fila é uma leitura no banco mais uma ida ao Redis — o mesmo
número de idas de hoje, com um `HSET` a mais dentro do script que já existia.

**Constraints**: mypy strict sem relaxação nova; funções de 4 a 20 linhas;
arquivos abaixo de 500 linhas; nenhum `id` nu em payload nenhum; `apps.game.cards`
continua sem importar `apps.players`; nenhum teste de websocket toca o banco;
o socket de partida e seus frames (feature 009) e o relógio (feature 010) não
mudam; as três regras de deck da feature 001 são chamadas, nunca reescritas.

**Scale/Scope**: 14 módulos novos, 15 editados, 1 migração, 2 fakes novos, 11
arquivos de teste novos e 2 editados.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | `Decisões/0001` em vigor: um perfil por usuário, `profile.pk == user.id`. O deck pendura em `PlayerProfile`, e `profile_id` **é** o `user_id`. As três regras de deck da feature 001 são chamadas como estão. Nenhuma nota nova é escrita. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | `card_id`, `deck_id`, `user_id`, `match_id`. O serializador mapeia `deck_id = source="pk"`; o payload de carta nomeia `card_id` e `card_type`. Um teste varre a resposta do catálogo e a do deck atrás de chave `id`. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | `QueueEntry` é `dataclass` congelada; a porta de deck é `Protocol`; o tradutor de `DeckProblem` fecha com `match` + `assert_never`; `Deck` e `CardId` são os tipos que a feature 001 já exporta. Nenhuma relaxação nova em `mypy.ini`. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | Um módulo por pergunta: o que o deck é (`models/deck.py`), o que é um deck aceitável (`deck_validation.py`), como se lê (`deck_queries.py`), como se escreve (`deck_writes.py`), como um problema vira JSON (`deck_problem_payload.py`), como o deck inicial nasce (`starter_deck_creation.py`), como uma carta vira payload (`card_payload.py`). O consumer ganha um handler e perde `deck_for`. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | `FakePlayerDeckSource` novo; `FakeCardCatalog` e `FakeMatchStore` reusados. Nenhum stub inline. Teste por função nova, e o cenário "deck editado entre o join e o par" é a regressão que a feature existe para impedir. |
| Stack fixada | ✅ PASS | Nada de novo em `requirements.txt` nem em `requirements-dev.txt`. |
| Injeção de dependência | ✅ PASS | O deck chega ao consumer por `as_asgi(decks=...)`, ao lado das cinco dependências que já entram assim. O catálogo entra por parâmetro em `starter_deck_creation` e em `deck_validation`. Nenhum módulo alcança global no momento da chamada. |
| Wrapper de terceiros | ✅ PASS | O Redis continua atrás de `MatchmakingQueue`, que agora também é dona do formato JSON do deck na chave. O ORM fica atrás de `deck_queries` / `deck_writes`; o consumer só conhece o `Protocol`. |
| Logging estruturado | ✅ PASS | Recusa de entrada na fila sai em JSON com `user_id`, `deck_id` e o código — o mesmo formato das recusas da 010. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy` e `black` sem configuração nova. |

**Resultado**: PASS. Re-verificado depois da Fase 1: nenhuma relaxação de mypy,
nenhuma dependência nova, nenhuma regra de deck reescrita, e nenhum caminho que
distinga deck alheio de deck inexistente. **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/011-deck-catalog-api/
├── plan.md                      # este arquivo
├── spec.md
├── research.md                  # D1–D17
├── data-model.md                # tabela, payloads, entrada de fila, recusas
├── quickstart.md
├── checklists/requirements.md
├── contracts/
│   ├── http_catalog.md          # GET game/cards/
│   ├── http_decks.md            # players/decks/, e o 404 indistinguível
│   └── matchmaking_messages.md  # join_queue e as três recusas novas
└── tasks.md                     # Fase 2 (/speckit-tasks — não sai daqui)
```

### Source Code

```text
server/
└── apps/
    ├── game/
    │   ├── card_payload.py                  # NOVO: carta -> payload, com a forma do efeito
    │   ├── card_catalog_view.py             # NOVO: GET game/cards/, com o payload em cache
    │   ├── urls.py                          # EDITADO: path("cards/", ...)
    │   ├── cards/
    │   │   ├── client.py                    # NOVO: get_card_catalog(), o handle do processo
    │   │   ├── __init__.py                  # EDITADO: reexporta get_card_catalog
    │   │   └── starter_deck.py              # EDITADO: docstring — deixa de ser andaime
    │   ├── protocol/
    │   │   ├── matchmaking_refusals.py      # NOVO: deck_not_specified, deck_not_found, invalid_deck
    │   │   └── __init__.py                  # EDITADO: reexporta os três
    │   ├── matchmaking/
    │   │   └── queue.py                     # EDITADO: QueueEntry, hash de decks, dois scripts Lua
    │   └── consumers/
    │       ├── base.py                      # EDITADO: send_refusal ganha **details opcional
    │       └── matchmaking.py               # EDITADO: handle_join_queue, profile_for; deck_for sai
    └── players/
        ├── models/
        │   ├── deck.py                      # NOVO: PlayerDeck
        │   └── __init__.py                  # EDITADO: reexporta os quatro modelos
        ├── migrations/
        │   └── 0002_playerdeck.py           # NOVO
        ├── services/
        │   ├── deck_validation.py           # NOVO: nome, teto 20, deck_problems da 001
        │   ├── deck_queries.py              # NOVO: leitura do dono + PlayerDeckSource
        │   ├── deck_writes.py               # NOVO: criar, renomear, trocar lista, apagar
        │   ├── deck_problem_payload.py      # NOVO: DeckProblem -> JSON, match + assert_never
        │   ├── starter_deck_creation.py     # NOVO: o deck inicial
        │   └── player_creation.py           # EDITADO: cria o deck inicial na mesma transação
        ├── deck_serializers.py              # NOVO: leitura, escrita e DeckWriteFields
        ├── deck_views.py                    # NOVO: as cinco operações
        ├── admin.py                         # EDITADO: PlayerDeck registrado
        └── urls.py                          # EDITADO: decks/ e decks/<deck_id>/

testes
├── apps/game/tests/
│   ├── fake_player_deck_source.py           # NOVO
│   ├── fake_matchmaking_queue.py            # NOVO: fila em memória, para os testes de socket
│   ├── test_effect_shape_matches_engine.py  # NOVO: a forma servida prevê o veredito do motor
│   ├── test_queued_deck_is_frozen.py        # NOVO (US6)
│   ├── test_card_payload.py                 # NOVO
│   ├── test_card_catalog_view.py            # NOVO
│   ├── test_matchmaking_join.py             # NOVO
│   ├── test_matchmaking_queue.py            # EDITADO: QueueEntry
│   └── test_matchmaking_clock.py            # EDITADO: consumer ganha decks=
└── apps/players/tests/
    ├── test_deck_model.py                   # NOVO
    ├── test_deck_validation.py              # NOVO
    ├── test_deck_api.py                     # NOVO
    ├── test_deck_isolation.py               # NOVO
    ├── test_deck_queries.py                 # NOVO
    └── test_starter_deck_creation.py        # NOVO
```

**Structure Decision**: convenção do Django, com o deck em `apps.players`
porque deck é posse de jogador, e o catálogo em `apps.game` porque catálogo é
do jogo. A direção de importação existente (`apps.game` → `apps.players`) é
preservada, e `apps.game.cards` continua folha — sem ciclo. Ver research D1.

## Ordem de execução

A Parte 1 não depende da Parte 2 e pode ser mergeada sozinha.

1. **Catálogo** — `card_payload.py`, `card_catalog_view.py`, `urls.py` e os dois
   testes. Entrega a US1 e a US2 inteiras.
2. **Modelo e validação** — `deck.py`, migração, `deck_validation.py`,
   `deck_problem_payload.py` e testes. Nada exposto ainda.
3. **API de decks** — serializador, view, rotas, e os testes de CRUD e de
   isolamento. Entrega a US3 e a US4.
4. **Deck inicial** — `starter_deck_creation.py`, `player_creation.py`,
   docstring de `starter_deck.py`. Entrega a US7.
5. **Fila e socket** — `QueueEntry` e os scripts Lua, `PlayerDeckSource`,
   `handle_join_queue`, códigos de recusa, `deck_for` removido. Entrega a US5 e
   a US6, e é o passo que exige os quatro anteriores.

O passo 5 é o único que muda comportamento existente; os testes de regressão do
matchmaking, do setup e do relógio rodam com ele.

## Desvios do plano, durante a execução

Três, todos pequenos e todos para fechar uma folga que o plano não tinha visto:

- **`apps/game/cards/client.py`** (`get_card_catalog`). O plano deixava cada
  consumidor chamar `mvp_catalog()`, que **constrói e valida** um catálogo novo
  a cada chamada. Com a view de decks, a de catálogo e o consumer, seriam três
  instâncias por processo. Um handle em cache, no formato de
  `matchmaking/client.py`, é o padrão da casa.
- **`MatchmakingConsumer.profile_for`**. O pareamento lê o perfil no banco, e
  essa linha derrubava os testes de socket contra a regra do `conftest.py` --
  nenhum teste de websocket toca o banco. Um método próprio dá a costura que os
  testes substituem, mantendo o caminho do **deck** o de produção, que é o que
  US6 precisa provar.
- **`FakeMatchmakingQueue`**. Fake nomeado para os testes do consumer, que
  precisam saber quem entrou e com que deck -- não que o pareamento seja
  indivisível, que é o que o Redis de verdade prova em
  `test_matchmaking_queue.py`.

E uma correção de desenho durante US3: as recusas de deck saem como `Response`
de 400, não como `ValidationError`. O DRF converte todo valor de uma
`ValidationError` em `ErrorDetail`, e `card_id`, `count` e `limit` chegariam ao
cliente como texto -- os problemas de deck precisam dos números.

## Riscos

| Risco | Mitigação |
|---|---|
| O cliente Unity hoje entra na fila só conectando; com a mudança, ele conecta e nada acontece | É quebra deliberada de protocolo do socket de matchmaking, registrada em `contracts/matchmaking_messages.md`. Não há produção. |
| `LREM` por valor quebraria se a entrada virasse um blob JSON na lista | A lista continua guardando só `user_id`; o deck vai para hash paralelo no mesmo script (D10). O teste de reentrada já existente cobre. |
| Teste de socket passar a tocar o banco e quebrar o `conftest` | O deck chega por porta injetada, com fake nomeado (D11). |
| `models/__init__.py` vazio faria um modelo novo não ser registrado | Passa a reexportar os quatro modelos com `__all__` (D15). |

## Complexity Tracking

Nenhuma violação da constituição a justificar. A tabela fica vazia de propósito.
