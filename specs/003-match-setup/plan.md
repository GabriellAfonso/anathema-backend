# Implementation Plan: Setup de Partida

**Branch**: `003-match-setup` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-match-setup/spec.md`

## Summary

A §3 do Fluxo de Partida vira código, e o motor de regras nasce com ela. Um
pacote novo, `apps/game/engine/`, recebe os quatro passos que transformam dois
decks em uma partida jogável: validar e materializar, embaralhar e comprar 4,
o mulligan, e o sorteio do token com a compensação. `Match.start` e
`MatchStore.create` — que hoje produzem uma partida válida e não jogável — são
removidos; quem cria partida passa a ser `engine.start_match`, e quem grava
chama `store.save`.

Quatro decisões sustentam o plano. **O motor sai de `match/`**: aquele pacote
declara no próprio docstring que nada ali é regra, e embaralhar, comprar e
sortear são regra — `engine/` é onde o Upkeep da §4 e o combate da §7 também
vão morar (D1). **A aleatoriedade é endereçada, não guardada**: a partida
carrega uma semente e um contador de sorteios, e cada operação abre um fluxo
próprio derivado de `(semente, ordinal)` — assim o mulligan que chega em outro
worker continua a mesma sequência sem que ninguém precise serializar um gerador
nem contar quantos números cada embaralhamento consome (D2). **A espera é um
booleano por jogador**, e "de quem estou esperando" é derivado dele, nunca um
segundo campo a manter em sincronia (D3). **A mutação concorrente é
compare-and-swap**: a partida passa a ser um hash Redis com `state` e
`version`, e `MatchStore.mutate` só grava se ninguém escreveu no meio — o
mulligan simultâneo é o primeiro read-modify-write real do projeto, e o
`store.py` já registrava essa dívida (D6).

Uma consequência que o plano assume de frente: dono do token e prioridade
passam a ser `int | None`, `None` durante a espera do mulligan. A spec mata o
"valor de espera" que existe hoje, e `None` é a afirmação honesta que o mypy
obriga todo leitor a tratar (D4).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova. Biblioteca padrão (`random`, `secrets`,
`dataclasses`, `enum`, `typing`, `json`), mais o que já existe no projeto:
`deck_problems`/`ensure_valid_deck` e `CardCatalog` de `apps.game.cards`
(feature 001) e o estado inteiro de `apps.game.match` (feature 002).
`redis.asyncio` continua sendo tocado só por `store.py`.

**Storage**: Redis 8.6, pela `MatchStore` que já existe. Uma chave por partida,
TTL de 6 horas. A chave muda de string para **hash** de dois campos, `state` e
`version` — a versão existe só para o compare-and-swap, e não é versão de
esquema. Sem banco relacional: esta feature não cria migration.

**Testing**: pytest 9.1 + pytest-django 4.14 + pytest-asyncio 1.4 (modo auto),
com `cd server && pytest`. Os testes de setup, mulligan e determinismo são
síncronos e sem I/O. Os de store e o de concorrência rodam contra um Redis real
no banco 15, pela fixture que já existe em `conftest.py`.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`),
uvicorn com múltiplos workers — a razão de o mulligan precisar de CAS e de a
semente morar na partida.

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`.
Não expõe HTTP. O websocket consome o pacote, mas o envelope da mensagem de
mulligan está fora de escopo.

**Performance Goals**: o setup roda uma vez por partida. O caminho quente é
`mutate`: uma leitura de hash, uma passada de serialização e um script de duas
linhas por resposta de mulligan — duas por partida. Embaralhar 40 cartas duas
vezes por jogador e sortear entre dois jogadores é ruído. O CAS retenta no
máximo 3 vezes, e com dois escritores possíveis a segunda tentativa já é o pior
caso realista.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`, sem relaxação nova em `mypy.ini`; funções de 4 a 20
linhas; arquivos abaixo de 500 linhas; nenhum campo `id` nu; nenhuma chave de
objeto JSON indexada por `user_id`; nenhum import de `random` fora de
`apps/game/randomness.py`.

**Scale/Scope**: 2 jogadores, 80 cartas, 5 sorteios por partida. 6 módulos
novos (1 de aleatoriedade, 4 de motor, 1 de deck de andaime), 9 editados,
5 arquivos de teste novos e 6 existentes atualizados, 2 fakes novos.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | Os nove passos vêm da §3 de `Game/Fluxo de Partida.md`, na ordem dela. As constantes (40, 20, 4, 5, 0) vêm da §12. `draw_from_deck_top` existe porque a §9 diz que toda compra do jogo passa pela mesma regra. O que a §13 registra em aberto — timeout — fica em aberto. Nada contradiz uma nota. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | Campos novos: `random_seed`, `next_roll_ordinal`, `mulligan_taken`, `token_holder_user_id`, `priority_user_id`. Tipos novos nomeados: `RandomSeed` (NewType sobre str), `Roll.ordinal`. Nenhum `id`. As recusas citam `user_id` e `card_instance_id` pelo nome. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | Só stdlib tipada. `RandomSource` é `Protocol` com `TypeVar`; `Roll` e `MatchEntry` são dataclasses congeladas. `int \| None` no dono do token obriga o mypy a cobrar o tratamento de quem lê. Nenhuma relaxação nova em `mypy.ini`. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | 6 módulos novos, um por passo, nenhum passando de ~120 linhas. `store.py` vai de 70 para ~140, ainda longe do teto. `record_mulligan` fica em ~15 linhas porque a validação e os quatro movimentos são funções próprias. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | `ScriptedRandomSource` e `fake_setup.py` novos; `FakeCardCatalog` e `FakeMatchStore` reaproveitados. O `ScriptedRandomSource` leva a asserção estática de conformidade de `Protocol` que `fake_card_catalog.py` já usa. Nenhum `lambda` de aleatoriedade inline. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova, nenhum bump. `random` e `secrets` são stdlib. |
| Estrutura Django previsível | ✅ PASS | `apps/game/engine/` é pacote de domínio dentro do app que já existe. Sem app novo, sem `INSTALLED_APPS`, sem migration, sem URL. |
| Injeção de dependência | ✅ PASS | Catálogo, fonte de aleatoriedade e semente chegam por parâmetro a `start_match`; a fonte chega por parâmetro a `record_mulligan`. `apps/game/randomness.py` é o único lugar do projeto que importa `random` — a interface própria que a constituição exige para embrulhar biblioteca de fora. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy`, `black` rodam sem configuração nova. |
| Comentários preservados no refactor | ⚠️ ATENÇÃO | Dois comentários existentes mudam de verdade e precisam ser **reescritos**, não apagados: o de `Match.start` que chama o dono do token de "valor de espera, não regra" (some junto com o método, e a razão vira o docstring de `finish_setup`) e o de `store.py` que diz "não existe caminho de mutação até os handlers de gameplay entrarem" (deixa de ser verdade nesta feature). Detalhe em [research.md](./research.md) D6 e D8. |

### Reverificação depois da Fase 1

O desenho fechado não mudou nenhum veredito. Cinco pontos que a Fase 1 tornou
concretos:

- **Princípio II**: `Roll` foi batizado assim, e não `Draw`, exatamente por
  causa da regra de nome único: "draw" já é compra de carta neste domínio
  (`draw_from_deck_top`), e duas leituras da mesma palavra no mesmo pacote é a
  ambiguidade que a regra existe para impedir. `roll` não tem nenhuma
  ocorrência em `apps/` hoje.
- **Princípio III**: a mudança de `token_holder_user_id` para `int | None`
  propaga para `player_view.py`, que declara o campo no `PlayerView`. É custo
  contabilizado, não surpresa — e é o mypy fazendo o trabalho que a spec pediu
  ao matar o valor de espera.
- **Princípio IV**: o maior módulo novo previsto é `mulligan.py`, com a
  validação, os quatro movimentos e duas exceções, na casa de 120 linhas. O
  maior editado é `store.py`, ~140. Os dois dentro do teto.
- **Princípio V**: o único I/O novo é o script Lua de CAS, e ele tem teste de
  contrato próprio contra o Redis do banco 15, no formato que
  `test_matchmaking_queue.py` já usa para o script de pareamento.
- **Injeção**: `SeededRandomSource` não guarda estado entre chamadas, então o
  ponto de composição pode ter uma instância só. Onde ela é construída para o
  matchmaking é decisão de `consumers/matchmaking.py`, no mesmo formato de
  `get_match_store()` — construtor com padrão, sobrescrito nos testes.

## Project Structure

### Documentation (this feature)

```text
specs/003-match-setup/
├── plan.md                    # Este arquivo
├── spec.md                    # A especificação
├── research.md                # Fase 0 — 12 decisões de desenho e alternativas
├── data-model.md              # Fase 1 — campos, invariantes, transições, contagens
├── quickstart.md              # Fase 1 — como rodar e provar que funciona
├── contracts/
│   └── match_setup.md         # Fase 1 — superfície pública das três camadas
├── checklists/
│   └── requirements.md        # Checklist de qualidade da spec (16/16)
└── tasks.md                   # Fase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
server/
└── apps/
    └── game/
        ├── randomness.py                    # NOVO — RandomSeed, Roll, RandomSource,
        │                                    #        SeededRandomSource, new_random_seed
        ├── engine/                          # NOVO — o motor de regras começa aqui
        │   ├── __init__.py                  # NOVO — superfície pública, __all__
        │   ├── card_draw.py                 # NOVO — draw_from_deck_top, EmptyDeckError
        │   ├── match_setup.py               # NOVO — MatchEntry, start_match,
        │   │                                #        finish_setup, InvalidPlayerDeckError
        │   └── mulligan.py                  # NOVO — record_mulligan + 2 recusas
        ├── cards/
        │   ├── starter_deck.py              # NOVO — deck de andaime do matchmaking
        │   ├── __init__.py                  # EDITADO — exporta starter_deck
        │   ├── deck_rules.py                # existente — reaproveitado, não alterado
        │   └── catalog.py                   # existente — não alterado
        ├── match/
        │   ├── match_state.py               # EDITADO — MatchPhase.MULLIGAN, semente,
        │   │                                #   ordinal, mint_roll, awaiting_...,
        │   │                                #   token/prioridade opcionais, sem start()
        │   ├── player_state.py              # EDITADO — mulligan_taken
        │   ├── documents.py                 # EDITADO — 3 campos, 2 tipos afrouxados
        │   ├── serialization.py             # EDITADO — os mesmos 3 campos
        │   ├── player_view.py               # EDITADO — token/prioridade opcionais
        │   ├── store.py                     # EDITADO — hash, mutate + CAS, sem create
        │   ├── __init__.py                  # EDITADO — __all__
        │   ├── cards_in_play.py             # existente — não alterado
        │   ├── modifiers.py                 # existente — não alterado
        │   ├── spell_stack.py               # existente — não alterado
        │   └── client.py                    # existente — não alterado
        ├── consumers/
        │   ├── matchmaking.py               # EDITADO — start_match + save, decks,
        │   │                                #   catálogo e fonte injetados
        │   └── match.py                     # existente — não alterado
        └── tests/
            ├── fake_random_source.py        # NOVO — ScriptedRandomSource
            ├── fake_setup.py                # NOVO — partidas já passadas pelo setup
            ├── test_match_setup.py          # NOVO — US1 e US4
            ├── test_mulligan.py             # NOVO — US2, a ordem e as 4 recusas
            ├── test_setup_randomness.py     # NOVO — US5, determinismo e recarga
            ├── test_card_draw.py            # NOVO — o movimento compartilhado
            ├── test_starter_deck.py         # NOVO — o andaime passa em deck_problems
            ├── fake_match_state.py          # EDITADO — constrói Match direto
            ├── fake_match_store.py          # EDITADO — sem create, com mutate
            ├── test_match_store.py          # EDITADO — hash, mutate, concorrência
            ├── test_match_state.py          # EDITADO — fase padrão, mint_roll, espera
            ├── test_match_serialization.py  # EDITADO — os 3 campos novos
            └── test_match_consumer_access.py # EDITADO — start_match + save
```

**Structure Decision**: um pacote `engine/` novo, irmão de `cards/` e `match/`,
plano, com `__all__` explícito. A alternativa barata — `match/setup.py` —
contradiz o docstring que a feature 002 escreveu para aquele pacote: *"Nada
aqui é regra de jogo (...) O estado é dado; quem o transforma é o motor."* O
setup transforma. `engine/` é onde o Upkeep da §4, a compra geral da §9 e o
combate da §7 vão cair, e criá-lo agora com um módulo por passo evita que o
motor nasça espalhado entre `match/` e os consumers. A razão longa está em
[research.md](./research.md) D1.

`randomness.py` fica um nível acima, direto em `apps/game/`, porque não é nem
estado nem regra: `match/` precisa de `RandomSeed` e `Roll` para guardá-los, e
`engine/` precisa de `RandomSource` para consumi-los. Um módulo só, sem pacote,
porque é uma responsabilidade só.

Testes continuam em `apps/game/tests/`, no nível plano que já existe, como
manda a constituição.

## Complexity Tracking

Nenhuma violação de princípio a justificar. Quatro pontos que esta feature
toca e resolve ou registra:

| Ponto | O que é | Encaminhamento |
|---|---|---|
| Dívida de atomicidade do `store.py` | O docstring diz: *"um read-modify-write (jogar uma carta) ainda não é atômico -- não existe caminho de mutação até os handlers de gameplay entrarem. Quando entrarem, a mutação vai precisar de script Lua, como o pareamento da fila."* | **Resolvida aqui.** O mulligan simultâneo é o primeiro caminho de mutação, e o CAS de `mutate` é a peça que todo caminho futuro reusa. O comentário é reescrito, não apagado: ele registra por que a peça existe. |
| `token_holder_user_id` vira opcional | Propaga para `player_view.py` e para todo leitor do dono do token. | Aceito e contabilizado (D4). É o preço de matar o valor de espera que a spec manda matar (FR-051), e o mypy é quem cobra — não a revisão. |
| Deck de andaime no matchmaking | A origem real do deck é outra feature; o consumer precisa entregar alguma coisa hoje. | `cards/starter_deck.py`, derivado do catálogo, com docstring dizendo que é andaime e qual feature o substitui. Tem teste próprio provando que passa em `deck_problems()`. |
| `play_card` roteado para o vazio | `consumers/base.py:155` roteia `{"type": "play_card"}` para um handler que `MatchConsumer` não implementa. | Continua fora de escopo, como o plano da feature 002 já registrou. Jogar carta é regra da Fase de Ação, e o `engine/` que esta feature cria é onde ela vai cair. |

**Registro no vault**: nada novo para `Backend/TODO.md`. O timeout de mulligan
já está registrado na §13 do Fluxo de Partida como pendência de transporte, e
esta feature não muda esse status.
