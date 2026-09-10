---

description: "Task list for 005-round-cycle"
---

# Tasks: Ciclo de Rodada

**Input**: Design documents from `specs/005-round-cycle/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/player_action.md](./contracts/player_action.md),
[contracts/round_cycle.md](./contracts/round_cycle.md),
[quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. Não é preferência de estilo — o princípio
V da constituição exige teste para toda função nova, e o quickstart põe
`pytest` como porta de conclusão.

**Organization**: agrupadas por história de usuário, na ordem que as
dependências permitem. Onde a ordem diverge da numeração da spec, a razão está
escrita na fase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a que história pertence (US1 a US8)
- Todo caminho de arquivo é relativo à raiz do repositório

## Estratégia de corte

Esta feature é **aditiva**: cinco módulos novos que nascem sem chamador, e dois
arquivos existentes que só ganham linhas. Nenhuma porta pública muda de forma,
nenhum teste existente é alterado. A suíte fica verde em todo checkpoint de fase
e entre todas as tarefas.

Três pontos concentram o risco, e cada um está isolado numa tarefa só:

- **T005 — a mudança de casa de `CardNotInHandError`.** Definir em
  `player_action.py`, importar em `mulligan.py` e ajustar o `__all__` do pacote
  são a mesma edição. Separá-los deixa `engine/__init__.py` importando um nome
  que não existe, e isso derruba a suíte inteira, não um arquivo.
- **T033 antes de T035 — a cascata antes da porta.** `_settle` existe antes de
  `submit_action` existir. Assim nunca há um commit em que uma ação de jogador
  deixa a partida parada em `ROUND_END`.
- **T041 — a costura da pilha.** O ramo `STACK_RESOLUTION` ganha teste na mesma
  fase em que a cascata nasce, e não numa fase de polimento onde seria fácil
  esquecê-lo.

### Por que US7 vem primeiro

`player_action.py` define a forma da ação e as três guardas comuns. `play_unit`
importa dele, `round_cycle` importa dele, e o mulligan passa a importar dele.
É foundational por natureza — nenhuma outra história começa antes.

### Por que US2 e US5 vêm antes de US1, US3 e US4

`upkeep.py` e `round_end.py` são os dois corpos que a cascata atravessa, e os
dois são testáveis sozinhos: dá para chamar `run_upkeep` e `end_round` sobre um
estado montado à mão, sem porta pública nenhuma. Escrever a porta primeiro
obrigaria a deixá-la chamando função vazia durante duas fases.

US1 (o primeiro empurrão) depende de US2, porque `begin_round_cycle` é
literalmente "execute o Upkeep pendente".

### Por que US4 e US6 dividem uma fase

O cenário de aceitação 2 de US4 é *"a rodada fecha e a partida volta pronta para
agir na rodada seguinte"* — isso **é** a cascata. Entregar as duas separadas
significa entregar, numa fase inteira, um `submit_action` que deixa a partida
parada em `ROUND_END`. É exatamente a falha que a spec nomeou como decisiva:
passa em todo teste unitário e trava na primeira partida real.

As tarefas continuam etiquetadas uma a uma, e cada história continua com o
próprio critério de teste independente.

---

## Phase 1: Setup

**Purpose**: linha de base e o auxiliar que todas as histórias de recusa usam.

- [X] T001 Rodar `cd server && pytest`, `cd server && mypy` e `cd server && black --check .` e registrar as três verdes antes de tocar em qualquer arquivo
- [X] T002 [P] Criar `server/apps/game/tests/match_snapshot.py` com `match_snapshot(match: Match) -> MatchDocument`, envolvendo `to_match_document`, com docstring explicando por que a comparação campo a campo passa pela serialização e não por uma lista de campos escolhida a dedo

**Checkpoint**: suíte verde, auxiliar disponível.

---

## Phase 2: User Story 7 - A forma da ação e a recusa que nomeia o ofensor (Priority: P1) 🎯 MVP

**Goal**: existe um tipo de ação de jogador, e existem as três guardas comuns
que toda ação atravessa antes de qualquer regra específica.

**Independent Test**: construir uma `PassAction` e chamar
`ensure_action_allowed` contra uma partida montada à mão — a guarda devolve o
`PlayerState` do autor quando as três passam, e levanta a recusa certa, com o
valor ofensor como atributo, quando alguma falha.

**⚠️ CRITICAL**: nenhuma outra história começa antes desta fase fechar.

### Implementation for User Story 7

- [X] T003 [US7] Criar `server/apps/game/engine/player_action.py` com `ActionKind`, `PlayUnitAction`, `PassAction` e a união `PlayerAction`, conforme [contracts/player_action.md](./contracts/player_action.md) §1 — `frozen=True, slots=True`, `action_kind` e `allowed_phases` como `ClassVar`
- [X] T004 [US7] Acrescentar `IllegalActionError`, `NotYourPriorityError` e `PhaseForbidsActionError` a `server/apps/game/engine/player_action.py`, cada uma citando o valor ofensor na mensagem **e** guardando-o como atributo
- [X] T005 [US7] Mover `CardNotInHandError` de `server/apps/game/engine/mulligan.py` para `server/apps/game/engine/player_action.py` numa edição só: a classe (com o docstring intacto) passa a herdar de `IllegalActionError`, `mulligan.py` passa a importá-la de `player_action`, e `server/apps/game/engine/__init__.py` passa a reexportá-la de lá
- [X] T006 [US7] Implementar `ensure_action_allowed` em `server/apps/game/engine/player_action.py`, com as três guardas na ordem de FR-044 e devolvendo o `PlayerState` do autor
- [X] T007 [US7] Acrescentar a `server/apps/game/engine/__init__.py` os nomes novos ao `__all__`: `ActionKind`, `PlayUnitAction`, `PassAction`, `PlayerAction`, `IllegalActionError`, `NotYourPriorityError`, `PhaseForbidsActionError`

### Tests for User Story 7

- [X] T008 [P] [US7] Criar `server/apps/game/tests/test_player_action.py` cobrindo a forma da ação: os `ClassVar` são os certos em cada braço, os braços são imutáveis, e um `PassAction` não tem onde guardar carta
- [X] T009 [US7] Em `server/apps/game/tests/test_player_action.py`, as três guardas comuns: `user_id` de fora levanta `NotAParticipantError`; sem prioridade levanta `NotYourPriorityError` citando quem tem; fase errada levanta `PhaseForbidsActionError` citando a fase
- [X] T010 [US7] Em `server/apps/game/tests/test_player_action.py`, a ordem das guardas: um autor sem prioridade **e** com a fase errada recebe a recusa de prioridade, e um `user_id` de fora recebe a de participante mesmo sem prioridade
- [X] T011 [US7] Em `server/apps/game/tests/test_player_action.py`, a atomicidade: para cada recusa de guarda comum, `match_snapshot` antes e depois é igual — contadores inclusive
- [X] T012 [US7] Rodar `cd server && pytest apps/game/tests/test_mulligan.py` e confirmar que passa **sem uma linha alterada** no arquivo — é a prova de que T005 não quebrou a feature 003

**Checkpoint**: a forma da ação existe e é testada. Nenhuma regra a usa ainda.

---

## Phase 3: User Story 2 - O Upkeep de toda rodada (Priority: P1)

**Goal**: a §4 executa sobre uma partida e a deixa na Fase de Ação com energia
recarregada e uma carta a mais em cada mão.

**Independent Test**: chamar `run_upkeep` sobre uma partida na rodada N com
energias gastas e conferir energia máxima N, energia atual N, uma carta a mais
em cada mão, passes em zero, prioridade no dono do token e fase de Ação.

### Implementation for User Story 2

- [X] T013 [US2] Criar `server/apps/game/engine/upkeep.py` com `MAX_ENERGY = 10`, `ENERGY_PER_ROUND = 1` e `_refill_energy(player)`, conforme [contracts/round_cycle.md](./contracts/round_cycle.md) §2 — as constantes com o comentário de origem na §12
- [X] T014 [US2] Implementar `_open_action_phase(match)` em `server/apps/game/engine/upkeep.py`: token disponível, passes em zero, prioridade no dono do token, fase de Ação
- [X] T015 [US2] Implementar `run_upkeep(match, *, randomness)` em `server/apps/game/engine/upkeep.py`, iterando `match.players` na ordem do par e chamando `draw_card` da feature 004 sem variante, com o docstring registrando que a garantia da §4 é independência e não indiferença à ordem

### Tests for User Story 2

- [X] T016 [P] [US2] Criar `server/apps/game/tests/test_upkeep.py` cobrindo a progressão de energia: rodada 1 dá 1, rodada N dá N, o teto de 10 se mantém na rodada 11 e nas seguintes
- [X] T017 [US2] Em `server/apps/game/tests/test_upkeep.py`, a recarga total: um jogador que sobrou com energia atual da rodada anterior fica com a máxima nova, nunca com a máxima mais o resto
- [X] T018 [US2] Em `server/apps/game/tests/test_upkeep.py`, a compra: cada jogador ganha 1 carta; um jogador com 10 na mão não compra e o Upkeep segue sem erro; um jogador com o deck vazio e o cemitério cheio dispara o reset da §9 e compra
- [X] T019 [US2] Em `server/apps/game/tests/test_upkeep.py`, o fim da fase: token disponível, passes em zero, prioridade no dono do token, fase de Ação, e nenhum Nexus nem banco tocados
- [X] T020 [US2] Em `server/apps/game/tests/test_upkeep.py`, a ordem fixa e a independência (FR-009a, FR-009b, SC-014): dois Upkeeps a partir do mesmo estado com os **dois** decks vazios e os dois cemitérios cheios produzem partidas idênticas; e o lado de um jogador termina igual quando só o estado do outro muda

**Checkpoint**: a §4 fecha sozinha, sem porta pública.

---

## Phase 4: User Story 5 - O Fim de Rodada (Priority: P1)

**Goal**: a §8 executa sobre uma partida, varre os modificadores temporários dos
dois bancos, troca o token, sobe a rodada e volta ao Upkeep.

**Independent Test**: pôr à mão um modificador temporário e um permanente em
unidades dos dois bancos, chamar `end_round`, e conferir que só os temporários
sumiram, que o token trocou de dono e que a rodada subiu 1.

**Nota**: esta fase é independente da Fase 3 e pode ser feita em paralelo com
ela — arquivos diferentes, nenhuma dependência entre os dois módulos.

### Implementation for User Story 5

- [X] T021 [US5] Criar `server/apps/game/engine/round_end.py` com `_lasting_modifiers(modifiers)` e `_sweep_expired_modifiers(player)`, filtrando por `EffectDuration.UNTIL_END_OF_ROUND` e deixando `damage_taken` intocado
- [X] T022 [US5] Implementar `_swap_token(match)` em `server/apps/game/engine/round_end.py`, estreitando `token_holder_user_id` com uma recusa nomeada em vez de `assert` ou `cast` (research.md D12)
- [X] T023 [US5] Implementar `end_round(match)` em `server/apps/game/engine/round_end.py` na ordem da §8 — varre, troca token, sobe rodada, põe a partida em `UPKEEP` — com o docstring registrando que executar o Upkeep **não** é daqui

### Tests for User Story 5

- [X] T024 [P] [US5] Criar `server/apps/game/tests/test_round_end.py` cobrindo a varredura: o temporário some, o permanente fica, uma unidade com os dois sobra com o permanente, e os bancos dos **dois** jogadores são varridos
- [X] T025 [US5] Em `server/apps/game/tests/test_round_end.py`, o que não é varrido: `damage_taken` continua o mesmo, e um banco vazio nos dois lados não é erro
- [X] T026 [US5] Em `server/apps/game/tests/test_round_end.py`, os três passos restantes: token no outro jogador, rodada N+1, fase `UPKEEP`; e nada de Nexus, mão, deck, cemitério ou composição de banco alterado
- [X] T027 [US5] Em `server/apps/game/tests/test_round_end.py`, que não existe descarte por excesso de mão: um jogador com 10 cartas na mão termina o Fim de Rodada com as mesmas 10

**Checkpoint**: a §8 fecha sozinha. As duas fases automáticas existem e são
testadas isoladamente.

---

## Phase 5: User Story 1 - Dar o primeiro empurrão (Priority: P1)

**Goal**: uma partida entregue pelo setup entra na Rodada 1 e para esperando
ação.

**Independent Test**: montar uma partida pelo setup, chamar
`begin_round_cycle`, e conferir que a fase é Fase de Ação, a rodada é 1, os dois
jogadores têm 1 de energia e cada um tem uma carta a mais na mão.

### Implementation for User Story 1

- [X] T028 [US1] Criar `server/apps/game/engine/round_cycle.py` com `MatchNotAwaitingUpkeepError`, citando a fase atual e a esperada, conforme [contracts/round_cycle.md](./contracts/round_cycle.md) §1
- [X] T029 [US1] Implementar `begin_round_cycle(match, *, randomness)` em `server/apps/game/engine/round_cycle.py`: recusa se a fase não for `UPKEEP`, delega a `run_upkeep`
- [X] T030 [US1] Acrescentar `begin_round_cycle` e `MatchNotAwaitingUpkeepError` ao `__all__` de `server/apps/game/engine/__init__.py`
- [X] T031 [US1] Acrescentar `fake_match_in_action_phase()` a `server/apps/game/tests/fake_setup.py`, que é `fake_match_ready_for_upkeep()` mais `begin_round_cycle`

### Tests for User Story 1

- [X] T032 [P] [US1] Criar `server/apps/game/tests/test_round_cycle.py` cobrindo o primeiro empurrão: fase de Ação, rodada 1, energia máxima e atual 1 dos dois lados, prioridade no dono do token
- [X] T033 [US1] Em `server/apps/game/tests/test_round_cycle.py`, as mãos: quem saiu do setup com 4 fica com 5, quem saiu com 5 fica com 6 (SC-001)
- [X] T034 [US1] Em `server/apps/game/tests/test_round_cycle.py`, as duas recusas: chamar de novo numa partida já iniciada, e chamar numa partida ainda em mulligan — as duas citam a fase e deixam `match_snapshot` idêntico

**Checkpoint**: a partida sai do setup e chega à Fase de Ação. Ninguém consegue
agir ainda.

---

## Phase 6: User Story 3 - Jogar unidade (Priority: P1)

**Goal**: a §5A existe como regra, com as quatro guardas na ordem e a mutação
depois de todas elas.

**Independent Test**: com 3 de energia, uma unidade de custo 2 na mão e o banco
vazio, chamar `play_unit` e conferir energia em 1, mão com uma carta a menos,
banco com uma unidade sem dano e sem modificador, e passes em 0.

### Implementation for User Story 3

- [X] T035 [US3] Criar `server/apps/game/engine/play_unit.py` com `MAX_BANK_SIZE = 6` e as três recusas — `CardIsNotAUnitError`, `NotEnoughEnergyError`, `BankIsFullError` — conforme [contracts/round_cycle.md](./contracts/round_cycle.md) §3, cada uma com os valores ofensores como atributos
- [X] T036 [US3] Implementar as quatro guardas de `server/apps/game/engine/play_unit.py` como funções próprias, na ordem carta na mão → carta é unidade → energia → banco, nenhuma delas mutando nada
- [X] T037 [US3] Implementar `play_unit(match, actor, action, *, catalog)` em `server/apps/game/engine/play_unit.py`: as quatro guardas, e só então descontar energia, tirar da mão, `bank.append(BankUnit(card=card))` e zerar os passes
- [X] T038 [US3] Acrescentar `CardIsNotAUnitError`, `NotEnoughEnergyError`, `BankIsFullError` e `MAX_BANK_SIZE` ao `__all__` de `server/apps/game/engine/__init__.py`

### Tests for User Story 3

- [X] T039 [P] [US3] Criar `server/apps/game/tests/test_play_unit.py` cobrindo a jogada aceita: energia descontada, carta fora da mão, unidade no banco com o mesmo `card_instance_id`, `damage_taken` em 0 e `modifiers` vazio
- [X] T040 [US3] Em `server/apps/game/tests/test_play_unit.py`, as bordas das guardas: energia exatamente igual ao custo é aceita e deixa a energia em 0; banco em 5 é aceito e vai a 6; unidade de custo 0 é jogável com 0 de energia
- [X] T041 [US3] Em `server/apps/game/tests/test_play_unit.py`, os efeitos colaterais: os passes zeram mesmo com o oponente já tendo passado uma vez, e o estado do oponente não muda em nada
- [X] T042 [US7] Em `server/apps/game/tests/test_play_unit.py`, as quatro recusas específicas — energia insuficiente citando custo e disponível, banco cheio citando o limite, carta fora da mão citando a carta, feitiço na ação errada citando o tipo — cada uma com `match_snapshot` idêntico antes e depois

**Checkpoint**: as duas fases automáticas e a regra da §5A existem. Falta a
porta que aceita a ação.

---

## Phase 7: User Story 4 + User Story 6 - Passar, a saída da fase e a cascata (Priority: P1)

**Goal**: uma ação de jogador entra pelo motor e a partida volta **já
estabilizada** — nunca em `UPKEEP`, nunca em `ROUND_END`.

**Independent Test (US4)**: com a partida na Fase de Ação e passes em 0, fazer o
jogador com prioridade passar e conferir passes em 1, prioridade no oponente e
fase ainda de Ação; fazer o oponente passar e conferir que a rodada virou.

**Independent Test (US6)**: com a partida na rodada 1 e passes em 1, executar um
único "passar" e conferir, numa única leitura, que a rodada é 2, o token trocou,
as energias são 2, cada mão ganhou 1 carta, os passes estão em 0 e a fase é a
Fase de Ação.

**Por que as duas juntas**: ver "Estratégia de corte" no topo. `_settle` (T043)
nasce **antes** de `submit_action` (T045), para que não exista commit em que uma
ação deixa a partida parada esperando outro empurrão.

### Implementation

- [X] T043 [US6] Implementar `_run_automatic_phase(match, randomness)` e `_settle(match, randomness)` em `server/apps/game/engine/round_cycle.py`, com o laço sobre `ROUND_END` e `UPKEEP` e o comentário registrando por que ele termina em no máximo duas voltas
- [X] T044 [US4] Implementar `CONSECUTIVE_PASSES_TO_EXIT = 2` e `_exit_action_phase(match)` em `server/apps/game/engine/round_cycle.py`, com as **duas** condições da §5 — pilha vazia leva a `ROUND_END`, pilha não vazia leva a `STACK_RESOLUTION` — e o comentário registrando que a segunda não tem consumidor nesta feature (research.md D9)
- [X] T045 [US4] Implementar `submit_action(match, action, *, catalog, randomness)` em `server/apps/game/engine/round_cycle.py`: `ensure_action_allowed`, o despacho `match` sobre a união, `_pass_priority`, `_exit_action_phase` e `_settle`, nesta ordem
- [X] T046 [US4] Implementar o braço do passe — soma 1 a `consecutive_passes` — e `_pass_priority(match, action)` em `server/apps/game/engine/round_cycle.py`, usando `action.actor_user_id`, que as guardas já provaram ser o dono da prioridade
- [X] T047 [US4] Acrescentar `submit_action` e `CONSECUTIVE_PASSES_TO_EXIT` ao `__all__` de `server/apps/game/engine/__init__.py`

### Tests

- [X] T048 [P] [US4] Criar `server/apps/game/tests/test_action_phase.py` cobrindo o passe: passes sobem 1, prioridade vai ao oponente, fase continua de Ação, e nenhuma zona de carta, energia ou Nexus muda
- [X] T049 [US4] Em `server/apps/game/tests/test_action_phase.py`, a alternância: `passar → jogar unidade → passar → passar` fecha a rodada só no último passe, porque a jogada quebrou a sequência
- [X] T050 [US4] Em `server/apps/game/tests/test_action_phase.py`, que a jogada de unidade também troca a prioridade e também passa pela saída da fase
- [X] T051 [US6] Em `server/apps/game/tests/test_round_cycle.py`, a cascata numa chamada: com passes em 1, um único `submit_action` devolve rodada 2, fase de Ação, passes 0, energias em 2, uma carta a mais em cada mão e o token no outro jogador
- [X] T052 [US6] Em `server/apps/game/tests/test_round_cycle.py`, dez rodadas seguidas: a partida chega à rodada 11, a fase é de Ação em 100% das leituras, e a energia máxima para em 10 (SC-002, SC-004, SC-005)
- [X] T053 [US6] Em `server/apps/game/tests/test_round_cycle.py`, a ordem da cascata: a varredura de modificadores acontece antes da troca de token, e a compra do Upkeep acontece com a rodada já subida (FR-042)
- [X] T054 [US6] Em `server/apps/game/tests/test_round_cycle.py`, a costura da pilha: com um `StackEntry` posto à mão, dois passes levam a partida a `STACK_RESOLUTION` e a cascata para ali; e ao longo de dez rodadas normais `match.stack` continua vazia
- [X] T055 [US6] Em `server/apps/game/tests/test_round_cycle.py`, que nenhum Nexus muda em nenhuma das dez rodadas (SC-010)

**Checkpoint**: a partida gira de ponta a ponta. É aqui que a feature está
funcionalmente completa.

---

## Phase 8: User Story 8 - Não quebrar 002, 003 e 004 (Priority: P2)

**Goal**: nenhuma das três features anteriores muda de comportamento.

**Independent Test**: rodar as suítes das features 002, 003 e 004 sem alteração
nenhuma nos testes delas, e conferir que passam.

- [X] T056 [US8] Em `server/apps/game/tests/test_round_cycle.py`, o round-trip: uma partida no meio de uma Fase de Ação, com unidades no banco e modificadores, passa por `to_match_document`/`match_from_document` e volta igual campo a campo (FR-056)
- [X] T057 [US8] Rodar `cd server && pytest apps/game/tests/test_match_setup.py apps/game/tests/test_mulligan.py apps/game/tests/test_setup_randomness.py apps/game/tests/test_card_draw.py apps/game/tests/test_deck_reset.py apps/game/tests/test_match_serialization.py` e confirmar que passam com `git diff` vazio nesses arquivos (SC-012)
- [X] T058 [US8] Confirmar com `git diff --stat` que `server/apps/game/match/`, `server/apps/game/cards/` e `server/apps/game/consumers/` não têm uma linha alterada

**Checkpoint**: a feature não deve nada às anteriores.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T059 Reescrever o docstring de `server/apps/game/engine/__init__.py`: as §4, §5 e §8 entraram, e a lista do que ainda falta encolhe para o combate da §7 e a pilha da §6
- [X] T060 [P] Conferir o `__all__` final de `server/apps/game/engine/__init__.py` contra [contracts/round_cycle.md](./contracts/round_cycle.md) §5, incluindo que `run_upkeep` e `end_round` **não** estão lá
- [X] T061 [P] Conferir que todo docstring público novo tem intenção mais um exemplo de uso, e que nenhum comentário existente foi apagado num refactor
- [X] T062 Rodar `cd server && black .` e depois `cd server && black --check .`
- [X] T063 Rodar `cd server && mypy` e confirmar verde sem relaxação nova em `server/mypy.ini`
- [X] T064 Rodar `cd server && pytest` inteiro
- [X] T065 Percorrer [quickstart.md](./quickstart.md) §3 no shell e conferir cada saída comentada

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 (Setup)
   │
   ▼
Phase 2 (US7 — a forma da ação)        ← BLOQUEIA tudo
   │
   ├──────────────┬───────────────┐
   ▼              ▼               ▼
Phase 3 (US2)  Phase 4 (US5)   Phase 6 (US3)
 Upkeep         Fim de Rodada   Jogar unidade
   │              │               │
   ▼              │               │
Phase 5 (US1)     │               │
 primeiro empurrão│               │
   │              │               │
   └──────────────┴───────────────┘
                  │
                  ▼
         Phase 7 (US4 + US6)
          a porta e a cascata
                  │
                  ▼
         Phase 8 (US8) → Phase 9 (Polish)
```

### Within Each User Story

- Implementação antes dos testes da mesma tarefa? **Não**: cada módulo nasce e
  os testes dele vêm na mesma fase, e a fase só fecha com a suíte verde.
- Recusas antes da regra que as levanta — a exceção precisa existir para o corpo
  poder citá-la.
- Guardas antes da mutação, dentro de cada regra. É a ordem que garante FR-048.

### Parallel Opportunities

- **T002** roda em paralelo com T001.
- **Fases 3 e 4** são inteiramente paralelas: `upkeep.py` e `round_end.py` não se
  conhecem, e `test_upkeep.py` e `test_round_end.py` são arquivos diferentes.
- **Fase 6** pode começar assim que a Fase 2 fechar, em paralelo com as Fases 3,
  4 e 5.
- Dentro de cada fase, a primeira tarefa de teste está marcada `[P]` porque cria
  um arquivo novo; as seguintes editam o mesmo arquivo e são sequenciais.
- **T060** e **T061** são leituras, e rodam em paralelo.

---

## Parallel Example: depois da Fase 2

```bash
# Três frentes independentes, três arquivos de módulo diferentes:
Task: "T013-T020 — engine/upkeep.py e tests/test_upkeep.py"
Task: "T021-T027 — engine/round_end.py e tests/test_round_end.py"
Task: "T035-T042 — engine/play_unit.py e tests/test_play_unit.py"
```

Nenhuma das três toca `round_cycle.py`, que só nasce na Fase 5.

---

## Implementation Strategy

### MVP

O MVP desta feature **não é uma história só**. US7 sozinha entrega um tipo sem
quem o consuma, e US2 sozinha entrega um Upkeep sem quem o chame. O menor
incremento que vale alguma coisa é **Fases 1 a 5**: a partida sai do setup,
entra na Rodada 1 com energia e compra, e para esperando ação. Dá para demonstrar
no shell, e é a metade automática do ciclo inteira.

### Entrega incremental

1. Fases 1-2 → a forma da ação existe e é testada.
2. Fases 3-5 → **a partida entra na Rodada 1 e para.** Demonstrável.
3. Fase 6 → jogar unidade existe como regra, sem porta.
4. Fase 7 → **a partida gira.** É a feature completa.
5. Fases 8-9 → a prova de que nada anterior quebrou, e as portas de qualidade.

### Parada útil

Entre a Fase 5 e a Fase 6 há um ponto de parada legítimo: a metade automática do
ciclo está pronta e testada, e a metade de entrada de jogador ainda não começou.
Se a feature precisar ser cortada, é aqui — e o que sobra é coerente, não meio
implementado.

---

## Notes

- `[P]` = arquivo diferente, sem dependência pendente
- Todo caminho é relativo à raiz do repositório
- A suíte fica verde **entre todas as tarefas**. Se alguma deixar vermelho, o
  corte descrito no topo foi violado
- Commit por tarefa ou por grupo lógico
- Nenhum arquivo de teste existente é alterado. Se um deles precisar mudar, a
  feature está quebrando uma anterior — pare e reveja
