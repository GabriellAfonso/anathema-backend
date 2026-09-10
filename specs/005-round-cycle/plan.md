# Implementation Plan: Ciclo de Rodada

**Branch**: `005-round-cycle` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-round-cycle/spec.md`

## Summary

As §4, §5 e §8 do Fluxo de Partida viram código, e o `engine/` ganha a primeira
regra que aceita entrada de jogador. Cinco módulos novos, um por
responsabilidade: `player_action.py` define a forma da ação e as três guardas
comuns; `play_unit.py` é a §5A; `upkeep.py` é a §4; `round_end.py` é a §8; e
`round_cycle.py` expõe as duas portas públicas — `begin_round_cycle`, o primeiro
empurrão que o setup deixou pendente, e `submit_action`, que recebe uma ação e
devolve a partida já estabilizada.

Duas decisões carregam a feature, e as outras existem para que elas fiquem como
estão.

**A forma da ação é uma união fechada de dataclasses** — `PlayerAction =
PlayUnitAction | PassAction` —, o mesmo idioma que `Card = Unit | Spell` e
`UnitModifier = ... | ...` já usam no projeto, com a mesma razão escrita nos dois:
um despacho que esqueça um braço é erro de mypy, não bug em produção. Cada braço
carrega os parâmetros que aquele tipo exige, e mais dois `ClassVar`:
`action_kind`, o discriminante, e `allowed_phases`, que é o que mantém a terceira
guarda comum de fato comum (D1, D3). Feitiço, ataque e bloqueio entram como
braços novos; nem a guarda nem a porta mudam.

**A cascata é um laço sobre fases automáticas**, não uma sequência fixa de
chamadas. `_exit_action_phase` decide entre Fim de Rodada e Resolução de Pilha, e
`_settle` atravessa o que estiver lá até a partida voltar a `ACTION` — no máximo
duas voltas, porque `ROUND_END` sempre leva a `UPKEEP` e `UPKEEP` sempre leva a
`ACTION` (D8). Um passe pode virar a rodada inteira dentro de uma chamada só, e
nenhum estado intermediário atravessa a fronteira da função.

O resto sustenta essas duas. **Valida tudo, muta depois** (D7): as quatro
perguntas de `play_unit` acontecem antes da primeira atribuição, e é a ordem —
não um rollback — que garante que uma recusa deixa o estado idêntico. **A recusa
é exceção** (D2), como o motor já faz para jogada ilegal, e o oposto do `None` da
compra da §9, de propósito: mão cheia é fluxo do jogo, jogada ilegal é entrada
inválida. **A ordem do Upkeep é a ordem do par** (D10), a resposta da sessão de
esclarecimento, com o contador de sorteios da partida intacto.

Uma tensão que o plano assume de frente: o ramo `STACK_RESOLUTION` é escrito e
fica sem quem o consuma. É o oposto do que a feature 004 fez ao apagar
`EmptyDeckError` por ser inalcançável, e a diferença está registrada em D9 — aquele
era inalcançável pela própria regra, para sempre; este é o encaixe que a §5
manda escrever e que a feature de pilha vai consumir. Dois testes o mantêm
honesto: um pinça o encaixe com um feitiço posto à mão, e outro afirma que a
pilha continua vazia ao longo de dez rodadas.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova, e nenhum import novo de terceiros. Só o
que já existe: `apps.game.match` (feature 002) para o estado, as zonas e os
modificadores; `apps.game.cards` (feature 001) para `CardCatalog`, `Unit`,
`CardType` e `EffectDuration`; `apps.game.engine.card_draw` (feature 004) para a
compra da §9; `apps.game.randomness` (feature 003) para `RandomSource`.

**Storage**: nenhuma mudança. **Nenhum campo novo no estado** — a §4, a §5A e a
§8 mexem só em campos que a feature 002 já modelou (`energy_max`,
`energy_current`, `hand`, `bank`, `modifiers`, `consecutive_passes`,
`priority_user_id`, `token_holder_user_id`, `token_consumed`, `round_number`,
`phase`). Então `documents.py` e `serialization.py` não são tocados, não há
migration, e FR-056 vale por construção.

**Testing**: pytest 9.1, com `cd server && pytest`. Todos os testes desta feature
são síncronos e sem I/O — inclusive o de round-trip, que passa por
`to_match_document`/`match_from_document` direto, sem Redis.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`), uvicorn
com múltiplos workers. Importa aqui por um motivo: o Upkeep compra, a compra pode
resetar o deck, e o sorteio do reset sai do contador que mora na partida — então
uma rodada virada depois de uma recarga do Redis continua a sequência de onde
parou.

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`. Não
expõe HTTP nem websocket. Nada em `consumers/` muda nesta feature.

**Performance Goals**: o caminho quente é uma ação de jogador. Passar é uma soma
e duas atribuições. Jogar unidade é uma busca linear numa mão de no máximo 10, um
`catalog.card()` (busca em `dict`) e três mutações de lista. A cascata acrescenta,
no máximo duas vezes por rodada, uma varredura dos dois bancos (no máximo 6
unidades cada) e duas compras.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`, sem relaxação nova em `mypy.ini`; funções de 4 a 20
linhas; arquivos abaixo de 500 linhas; nenhum campo `id` nu; nenhum import de
`random` fora de `apps/game/randomness.py`; nenhuma alteração nos arquivos de
teste das features 002, 003 e 004.

**Scale/Scope**: 5 módulos novos, 2 editados (`mulligan.py` e `__init__.py` do
pacote), 6 arquivos de teste novos, 1 auxiliar de teste novo e 1 fake estendido.
Nenhum arquivo de teste existente é alterado.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | As três regras vêm literalmente das §4, §5 e §8 de `Game/Fluxo de Partida.md`; os valores vêm da §12. "Entra pronta, não existe doença de invocação" é da §5A e do docstring de `BankUnit`, que já o afirma. A condição de saída da §5 é escrita como a nota manda, inclusive o braço que esta feature não consome (D9). Nenhuma nota nova é escrita. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | `actor_user_id` na ação, `card_instance_id` na carta, `user_id` e `match_id` nas recusas. Nenhum campo novo no estado, então nenhuma chance de `id` na serialização. `PlayUnitAction.card_instance_id` é `CardInstanceId`, o `NewType` da feature 002 — passar um `card_id` no lugar é erro de mypy. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | União fechada com `ClassVar` discriminante, `frozenset[MatchPhase]`, retornos `None` explícitos, `PlayerState` como retorno da guarda. Nenhum `Any`, nenhum `cast`, nenhuma relaxação nova. O único `int \| None` a estreitar é `token_holder_user_id`, e ele é estreitado com uma recusa nomeada, não com `assert` nem `cast` (D12). |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | Cinco módulos, um por seção, entre 40 e 120 linhas cada (D5). A função mais longa é `play_unit`, com ~10 linhas de corpo e 1 nível de indentação, porque as quatro guardas são funções próprias. A cascata é um `while` de 2 linhas sobre um despacho de 6. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | Nenhum I/O, então nenhum fake de I/O novo. `FakeCardCatalog`, `ScriptedRandomSource`, `SeededRandomSource`, `fake_match_state.py` e `fake_setup.py` já cobrem tudo. O único acréscimo é um auxiliar de fotografia de estado, que não é fake porque não substitui nada (D14). |
| Stack fixada | ✅ PASS | Nenhuma dependência nova, nenhum bump, nenhum import de terceiros. |
| Estrutura Django previsível | ✅ PASS | Cinco módulos dentro de um pacote que já existe. Sem app novo, sem `INSTALLED_APPS`, sem migration, sem URL, sem consumer. |
| Injeção de dependência | ✅ PASS | `catalog` e `randomness` chegam por parâmetro nomeado, como em `start_match` e `record_mulligan`. Nenhum módulo desta feature importa `random` nem chama `mvp_catalog()`. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy` e `black` rodam sem configuração nova. |
| Comentários preservados no refactor | ⚠️ ATENÇÃO | Três docstrings existentes deixam de ser previsão e viram fato; eles precisam ser **reescritos**, não apagados. Detalhe abaixo. |

### O que precisa ser reescrito, e por quê

Os três textos foram escritos prevendo esta feature. Nenhum está errado — todos
estão cumpridos, e o texto precisa passar do futuro para o presente.

1. **`engine/__init__.py`, docstring do pacote.** Hoje diz: *"Moram aqui o setup
   da §3 e a compra com reset de deck da §9. O Upkeep da §4 e o combate da §7
   caem no mesmo lugar quando entrarem."* A §4 entrou, e com ela a §5 e a §8; a
   lista encolhe para o combate. O `__all__` cresce com as portas públicas, a
   união da ação e as recusas.

2. **`match/match_state.py`, docstring do módulo.** Hoje diz: *"Nada aqui decide
   se uma jogada é legal, aplica dano, troca prioridade ou avança fase — isso é
   regra, e regra é do motor."* Continua verdade e **não muda**. Vale registrar
   aqui porque é a razão de `match/` não ser tocado por esta feature: a fronteira
   que aquele texto declara é exatamente a que o plano respeita.

3. **`engine/mulligan.py`, cabeçalho.** Não muda de conteúdo, mas perde a
   definição de `CardNotInHandError`, que migra para `player_action.py` (D4). O
   docstring da exceção vai junto, intacto — ele explica por que o identificador
   repetido cai na mesma recusa, e essa razão continua sendo dela.

Dois textos existentes passam a ser verificáveis por esta feature, e é bom que
não mudem:

- **`match/cards_in_play.py`, `BankUnit.modifiers`**: *"Entra pronta e sem buff:
  não existe doença de invocação (Fluxo de Partida §5A)."* FR-022 é o teste dessa
  frase, e `BankUnit(card=card)` a cumpre por construção — os dois campos têm
  default.
- **`match/player_state.py`, docstring do módulo**: *"Os tetos de mão (10) e de
  banco (6) da §12 **não** são validados aqui. Aplicá-los é regra — o de mão
  acontece na compra (§9), o de banco ao jogar unidade (§5A)."* Esta feature é a
  §5A chegando ao lugar que aquele texto reservou, e é por isso que
  `MAX_BANK_SIZE` mora em `play_unit.py` (D11).

### Reverificação depois da Fase 1

O desenho fechado não mudou nenhum veredito. Cinco pontos que a Fase 1 tornou
concretos:

- **Princípio II**: `submit_action` e `begin_round_cycle` foram pesados contra
  `start_match` e `finish_setup`, que já existem no pacote. `begin_round_cycle`
  ficou em vez de `begin_match` justamente porque `begin_match` e `start_match`
  diferem por uma palavra e fazem coisas diferentes — o tipo de par que a regra
  de nomes específicos existe para impedir.
- **Princípio III**: a guarda comum devolve o `PlayerState` do autor em vez de
  `None`. Ela já fez a busca para provar a guarda 1; devolver o resultado evita
  que cada regra específica repita `match.player(...)` e evita um segundo ponto
  onde `NotAParticipantError` poderia escapar.
- **Princípio IV**: o módulo maior depois da feature é `player_action.py`, na
  casa de 120 linhas — a união com dois braços, quatro recusas e a guarda comum.
  Longe do teto de 500. `round_cycle.py` fica em ~90.
- **Princípio IV, de novo**: `_exit_action_phase` e `_settle` são funções
  separadas de propósito. Decidir a saída da §5 e atravessar fase automática são
  duas coisas, e é a separação que deixa a feature de pilha acrescentar um braço
  em cada uma sem tocar na outra.
- **Princípio V**: `test_player_action.py` prova a atomicidade com uma foto do
  documento inteiro antes e depois, e não com uma lista de campos escolhidos a
  dedo. É o que faz FR-050 — os dois contadores — ser conferido sem que ninguém
  precise lembrar deles.

## Project Structure

### Documentation (this feature)

```text
specs/005-round-cycle/
├── plan.md                    # Este arquivo
├── spec.md                    # A especificação
├── research.md                # Fase 0 — 14 decisões de desenho e alternativas
├── data-model.md              # Fase 1 — campos tocados, transições, invariantes
├── quickstart.md              # Fase 1 — como rodar e provar que funciona
├── contracts/
│   ├── player_action.md       # Fase 1 — a forma da ação e as recusas
│   └── round_cycle.md         # Fase 1 — as portas públicas e as três regras
├── checklists/
│   └── requirements.md        # Checklist de qualidade da spec (16/16)
└── tasks.md                   # Fase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
server/
└── apps/
    └── game/
        ├── engine/
        │   ├── player_action.py         # NOVO — ActionKind, PlayUnitAction,
        │   │                            #   PassAction, PlayerAction,
        │   │                            #   IllegalActionError e as recusas,
        │   │                            #   ensure_action_allowed,
        │   │                            #   CardNotInHandError (vindo de mulligan.py)
        │   ├── play_unit.py             # NOVO — §5A: play_unit, MAX_BANK_SIZE
        │   ├── upkeep.py                # NOVO — §4: run_upkeep, MAX_ENERGY,
        │   │                            #   ENERGY_PER_ROUND
        │   ├── round_end.py             # NOVO — §8: end_round, a varredura
        │   ├── round_cycle.py           # NOVO — begin_round_cycle, submit_action,
        │   │                            #   a saída da §5 e a cascata
        │   ├── mulligan.py              # EDITADO — CardNotInHandError sai daqui
        │   ├── __init__.py              # EDITADO — __all__ e docstring do pacote
        │   ├── card_draw.py             # NÃO TOCADO — chamado pelo Upkeep como está
        │   ├── deck_reset.py            # NÃO TOCADO
        │   └── match_setup.py           # NÃO TOCADO — é a prova de FR-003
        ├── match/                       # NÃO TOCADO — nenhum campo novo
        ├── cards/                       # NÃO TOCADO
        ├── consumers/                   # NÃO TOCADO — transporte está fora de escopo
        ├── randomness.py                # NÃO TOCADO — reaproveitado
        └── tests/
            ├── test_upkeep.py           # NOVO — US2
            ├── test_play_unit.py        # NOVO — US3 e as recusas da §5A
            ├── test_action_phase.py     # NOVO — US4
            ├── test_round_end.py        # NOVO — US5
            ├── test_round_cycle.py      # NOVO — US1, US6, US8
            ├── test_player_action.py    # NOVO — US7
            ├── match_snapshot.py        # NOVO — auxiliar de foto de estado
            ├── fake_setup.py            # EDITADO — fake_match_in_action_phase()
            ├── fake_match_state.py      # reaproveitado, não alterado
            ├── fake_card_catalog.py     # reaproveitado, não alterado
            ├── fake_random_source.py    # reaproveitado, não alterado
            ├── test_match_setup.py      # NÃO TOCADO — é a prova de FR-003
            ├── test_mulligan.py         # NÃO TOCADO — importa do pacote, não do módulo
            ├── test_card_draw.py        # NÃO TOCADO — é a prova de FR-007
            ├── test_deck_reset.py       # NÃO TOCADO
            └── test_match_serialization.py  # NÃO TOCADO
```

**Structure Decision**: nenhum pacote novo. `engine/` continua plano, com um
módulo por regra, e a feature acrescenta cinco. A razão de não juntá-los num
`round_cycle.py` só está em [research.md](./research.md) D5: cada um tem uma razão
para mudar, e o grafo de dependência entre eles é um DAG raso —
`round_cycle` → {`upkeep`, `round_end`, `play_unit`, `player_action`}, e
`play_unit` → `player_action`. Nenhum ciclo, e cada regra é testável sem a
cascata.

`match/` não é tocado, e isso é resultado, não sorte: a §4, a §5A e a §8 só mexem
em campos que a feature 002 já modelou. É o que faz FR-056 — o round-trip pelo
Redis — valer sem uma linha nova de serialização.

`consumers/` também não é tocado. Quem chama `begin_round_cycle` e
`submit_action` é a feature de transporte, e a spec a põe fora de escopo.

## Complexity Tracking

Nenhuma violação de princípio a justificar. Cinco pontos que esta feature toca e
resolve ou registra:

| Ponto | O que é | Encaminhamento |
|---|---|---|
| O ramo `STACK_RESOLUTION` sem consumidor | `_exit_action_phase` decide por ele, e `_settle` não sabe atravessá-lo. Inalcançável enquanto nada empilha. | **Escrito de propósito** (D9). FR-016 o exige e a §5 o escreve. É o oposto do `EmptyDeckError` da feature 004 — a diferença está tabelada em D9. Dois testes o seguram: um pinça o encaixe com um feitiço posto à mão, outro afirma que a pilha continua vazia por dez rodadas. |
| Raiz dupla de recusa | O motor levanta `NotAParticipantError` (de `match/`) na guarda 1 e `IllegalActionError` nas demais. | **Aceito** (D2). Fazer a primeira herdar da segunda inverteria a dependência entre `match/` e `engine/`. O transporte pega as duas; o contrato documenta as duas. |
| `CardNotInHandError` muda de módulo | Sai de `mulligan.py`, entra em `player_action.py`, continua reexportada pelo pacote. | **Movida, não copiada** (D4). Nenhum teste muda, porque todos importam de `apps.game.engine`. |
| `mulligan.py` importando de `player_action.py` | O mulligan não é uma `PlayerAction` nesta feature, e mesmo assim depende do módulo que define a forma da ação. | **Registrado**. O módulo é "a forma da entrada de jogador e o que ela precisa provar", e a exceção cabe nisso. A spec já prevê que o mulligan vai reusar a forma da ação; quando isso acontecer, o import deixa de ser assimétrico. |
| `play_card` roteado para o vazio | `consumers/base.py:155` roteia `{"type": "play_card"}` para um handler que `MatchConsumer` não implementa. | **Continua fora de escopo**, como os planos das features 002, 003 e 004 registraram. Esta feature entrega a regra que aquele handler vai chamar; ligar os dois é a feature de transporte. Depois desta, o pendente deixa de ser "falta a regra" e passa a ser só "falta o envelope". |

**Registro no vault**: nada novo para `Backend/TODO.md`. O timeout de jogada
continua em aberto na §13 do Fluxo de Partida, é problema de transporte, e a spec
o põe fora de escopo por decisão — não por dívida desta feature.
