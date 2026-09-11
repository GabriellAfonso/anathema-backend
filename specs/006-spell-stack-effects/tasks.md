---

description: "Task list for 006-spell-stack-effects"
---

# Tasks: Pilha de Feitiços e Efeitos

**Input**: Design documents from `specs/006-spell-stack-effects/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/cast_spell.md](./contracts/cast_spell.md),
[contracts/stack_resolution.md](./contracts/stack_resolution.md),
[contracts/spell_effect.md](./contracts/spell_effect.md),
[quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. Não é preferência de estilo — o princípio
V da constituição exige teste para toda função nova, e o quickstart põe
`pytest` como porta de conclusão.

**Organization**: agrupadas por história de usuário, na ordem que as
dependências permitem. Onde a ordem diverge da numeração da spec, a razão está
escrita abaixo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a que história pertence (US1 a US9)
- Todo caminho de arquivo é relativo à raiz do repositório

## Estratégia de corte

Esta feature **não é aditiva como as anteriores**. Ela acrescenta estado ao
`match/` — o primeiro acréscimo desde a feature 002 — e mexe em dois arquivos de
produção da feature 005. A suíte precisa ficar verde em todo checkpoint de fase,
e para isso três edições precisam ser atômicas.

Quatro pontos concentram o risco, e cada um está isolado numa tarefa só:

- **T005 — a chave nova no `MatchDocument`.** Acrescentar o campo em
  `documents.py` sem escrever a ida e a volta em `serialization.py` deixa o
  `TypedDict` com uma chave que `to_match_document` não produz, e o mypy strict
  reprova o dicionário literal. As duas edições são a mesma tarefa.
- **T010 — a mudança de casa de `card_in_hand`, `ensure_enough_energy` e
  `NotEnoughEnergyError`.** Definir em `player_action.py`, passar `play_unit.py`
  a usá-las e ajustar o `__all__` do pacote são a mesma edição. Separá-las deixa
  `engine/__init__.py` importando um nome que não existe, e isso derruba a suíte
  inteira, não um arquivo. É o mesmo corte que a feature 005 fez com
  `CardNotInHandError` (research D16).
- **T057 antes de T059 — a resolução antes da cascata.** `resolve_stack` existe
  e é testada sobre um estado montado à mão **antes** de `STACK_RESOLUTION`
  entrar em `_AUTOMATIC_PHASES`. Na ordem contrária existe um commit em que a
  cascata entra numa fase que ninguém sabe atravessar, e o laço de `_settle`
  gira para sempre — a falha que o comentário da feature 005 nomeou.
- **T014 — a recusa da partida terminada.** `MatchIsOverError` e o ramo dentro da
  terceira guarda entram juntos. A classe sem o ramo é código morto; o ramo sem
  a classe não compila.

### Por que a ordem diverge da numeração da spec

A spec numera as histórias na ordem em que o jogador as vive: lançar, responder,
resolver, o exemplo da §6, os efeitos, o aplicador, a vitória, as recusas. A
ordem de construção é quase a inversa, porque **quem resolve depende de quem
aplica, e quem aplica depende de quem altera Nexus**.

| Fase | História | Depende de | Por quê |
|---|---|---|---|
| 2 | — | — | O estado terminal não é história nenhuma; é o tipo que a §10 grava. |
| 3 | US7 | Fase 2 | `change_nexus` é a porta que todo efeito de Nexus usa. |
| 4 | US5 | US7 | SACRIFICIAL FIRE e LIFE POTION chamam `change_nexus`. |
| 5 | US6 | US5 | "O aplicador não sabe de onde veio" é uma propriedade do que a Fase 4 escreveu. |
| 6 | US1 | Fase 2 | Empilhar não depende de aplicar. É a primeira coisa que um jogador faz. |
| 7 | US8 | US1 | As cinco recusas moram no mesmo módulo do lançamento. |
| 8 | US2 | US1 | Responder é lançar com a prioridade trocada — **nenhum código novo**. |
| 9 | US3 | US1 + US5 | A resolução drena o que o lançamento empilhou e chama o que a Fase 4 escreveu. |
| 10 | US4 | US3 | O exemplo canônico da §6 é a resolução mais o dano letal. |
| 11 | US9 | todas | Round-trip do estado que as anteriores produziram. |

### Por que US2 não tem tarefa de produção

"Responder no topo" já funciona quando US1 termina. A prioridade troca depois de
toda ação desde a feature 005, e é ela que dá a vez ao oponente; a pilha aceita
duas entradas porque é uma lista. A história continua com fase própria porque o
comportamento **precisa ser afirmado** — a ordem LIFO e o `caster_user_id` de
cada entrada são o que a Fase 9 vai consumir, e descobrir que estão errados lá
seria descobrir tarde.

### Por que a Fase 2 não é uma história

`MatchOutcome`, `MatchPhase.FINISHED` e `Match.outcome` são o tipo do desfecho,
não a regra que o produz. A regra é US7 e mora em `engine/victory.py`. Separá-los
é o que mantém `match/` dizendo de si mesmo, como sempre disse, que ali não há
regra de jogo.

---

## Phase 1: Setup

**Purpose**: confirmar que a base está verde antes de acrescentar estado a ela.

- [X] T001 Rodar `cd server && pytest && mypy && black --check .` e registrar a contagem de testes da suíte antes de qualquer edição, para que a Fase 11 possa comparar

**Checkpoint**: baseline conhecido. Nenhuma dependência nova é instalada, nenhuma migration é criada.

---

## Phase 2: Foundational — o estado terminal (Blocking Prerequisites)

**Purpose**: o tipo do desfecho da partida, a fase terminal e a serialização
deles. É o primeiro acréscimo de estado desde a feature 002.

**⚠️ CRITICAL**: nenhuma história começa antes desta fase. `victory.py` grava o
tipo que ela define, e `cast_spell.py` usa as guardas que ela move de casa.

- [X] T002 [P] Criar `server/apps/game/match/match_outcome.py` com `MatchOutcome` (`defeated_user_ids: tuple[int, ...]`, propriedade derivada `is_draw`) e `InvalidMatchOutcomeError`, validando na construção que há 1 ou 2 `user_id` distintos, conforme [contracts/spell_effect.md](./contracts/spell_effect.md) §5
- [X] T003 [P] Escrever `server/apps/game/tests/test_match_outcome.py` cobrindo `is_draw` nos dois casos e as três recusas de construção (vazio, três, repetido), cada uma citando o valor recebido
- [X] T004 Acrescentar `MatchPhase.FINISHED`, o campo `Match.outcome: MatchOutcome | None = None` e a propriedade derivada `Match.is_over` em `server/apps/game/match/match_state.py`, e atualizar o docstring de `MatchPhase` para registrar que `FINISHED` é terminal e está fora de `allowed_phases` de toda ação de propósito
- [X] T005 Acrescentar `MatchOutcomeDocument` e a chave `outcome: MatchOutcomeDocument | None` a `MatchDocument` em `server/apps/game/match/documents.py`, **e** a ida e a volta correspondentes em `server/apps/game/match/serialization.py` — as duas edições são atômicas (ver Estratégia de corte)
- [X] T006 [P] Acrescentar a chave `outcome: MatchOutcomeDocument | None` a `PlayerView` e preenchê-la em `build_player_view` em `server/apps/game/match/player_view.py`
- [X] T007 Acrescentar `MatchOutcome`, `MatchOutcomeDocument` e `InvalidMatchOutcomeError` ao `__all__` de `server/apps/game/match/__init__.py`
- [X] T008 [P] Escrever em `server/apps/game/tests/test_spell_state_round_trip.py` o primeiro caso: uma partida com `outcome` preenchido e fase `FINISHED` sobrevive a `to_match_document` → `json` → `match_from_document` campo a campo, e uma com `outcome=None` volta com `None`
- [X] T009 Rodar `cd server && pytest apps/game/tests/test_match_serialization.py apps/game/tests/test_player_view.py apps/game/tests/test_match_state.py` e confirmar que passam **sem nenhuma alteração nesses arquivos** (SC-017)
- [X] T010 Mover `card_in_hand`, `ensure_enough_energy` e `NotEnoughEnergyError` para `server/apps/game/engine/player_action.py`, passar `server/apps/game/engine/play_unit.py` a usá-las no lugar das cópias privadas, e ajustar o `__all__` de `server/apps/game/engine/__init__.py` — edição atômica, conforme research D16 e [contracts/cast_spell.md](./contracts/cast_spell.md) §3
- [X] T011 Rodar `cd server && pytest apps/game/tests/test_play_unit.py apps/game/tests/test_player_action.py` e confirmar que passam sem alteração nesses arquivos

**Checkpoint**: o desfecho é um tipo gravável e as guardas compartilhadas estão no módulo certo. A suíte inteira continua verde e nada mudou de comportamento.

---

## Phase 3: User Story 7 - A partida acaba quando um Nexus chega a zero (Priority: P1)

**Goal**: a §10 vira código. Depois de qualquer evento que altere um Nexus, um
jogador com Nexus ≤ 0 perde; os dois é empate; a partida terminada é
reconhecível e não aceita ação.

**Independent Test**: pôr um Nexus em 0 à mão, chamar `check_victory`, e conferir
que a partida está terminada com aquele jogador derrotado, que a fase é
`FINISHED`, e que qualquer ação subsequente dos **dois** jogadores é recusada
citando o resultado.

### Implementation for User Story 7

- [X] T012 [US7] Criar `server/apps/game/engine/victory.py` com `check_victory(match)` — idempotente, recusa alterar uma partida já terminada — e o privado `_finish_match(match, outcome)`, único ponto do código que escreve o par `(outcome, phase=FINISHED)`, conforme [contracts/spell_effect.md](./contracts/spell_effect.md) §4
- [X] T013 [US7] Acrescentar `change_nexus(match, player, amount)` a `server/apps/game/engine/victory.py`: soma o valor assinado e chama `check_victory`. **Sem teto e sem piso** — nenhuma constante de Nexus máximo, e negativo preservado como ficou (research D13)
- [X] T014 [US7] Acrescentar `MatchIsOverError(PhaseForbidsActionError)` a `server/apps/game/engine/player_action.py` e levantá-la de **dentro da terceira guarda** de `ensure_action_allowed` quando `match.phase is MatchPhase.FINISHED` — a ordem participante → prioridade → fase **não muda** (research D3). Classe e ramo entram juntos
- [X] T015 [US7] Acrescentar `change_nexus`, `check_victory` e `MatchIsOverError` ao `__all__` de `server/apps/game/engine/__init__.py`

### Tests for User Story 7

- [X] T016 [P] [US7] Escrever em `server/apps/game/tests/test_victory.py` os casos de derrota: Nexus em exatamente 0 derrota, Nexus negativo derrota e preserva o valor negativo, Nexus 1 não derrota
- [X] T017 [P] [US7] Acrescentar a `server/apps/game/tests/test_victory.py` o empate — os dois Nexus ≤ 0 no mesmo cálculo — e a idempotência: uma segunda chamada de `check_victory` não troca o resultado
- [X] T018 [P] [US7] Acrescentar a `server/apps/game/tests/test_victory.py` a invariante nos dois sentidos: `outcome is not None` ⟺ `phase is MatchPhase.FINISHED`, e que `change_nexus` sem cruzar o zero não termina a partida
- [X] T019 [US7] Acrescentar a `server/apps/game/tests/test_victory.py` a recusa: numa partida terminada, `submit_action` de **cada um dos dois jogadores** levanta `MatchIsOverError` citando os derrotados, e `match_snapshot` antes e depois é idêntico

**Checkpoint**: US7 completa. A §10 é executável e testável sozinha, sem que nenhum efeito exista ainda.

---

## Phase 4: User Story 5 - Os cinco efeitos do MVP (Priority: P1)

**Goal**: o motor altera vida, ataque e Nexus. Os cinco efeitos do catálogo
produzem exatamente o que a carta descreve, lidos pelos campos estruturados.

**Independent Test**: para cada um dos cinco, montar o estado mínimo, chamar
`apply_spell_effect` **direto** — sem pilha nenhuma — e conferir campo a campo o
que a carta descreve, e que nada além disso mudou.

### Implementation for User Story 5

- [X] T020 [P] [US5] Criar `server/apps/game/engine/unit_vitals.py` com `unit_max_health` (molde + modificadores de vida), `unit_remaining_health` (máxima − dano), `unit_is_dead` (restante ≤ 0) e `unit_has_damage_immunity`, conforme [contracts/spell_effect.md](./contracts/spell_effect.md) §2. **`unit_effective_attack` não entra** (research D9)
- [X] T021 [US5] Criar `server/apps/game/engine/unit_damage.py` com `deal_damage_to_unit(unit, amount)` — imunidade ativa faz nada entrar — e `bury_dead_units(match, *, catalog)`, que varre os **dois** bancos e move a carta para o cemitério do **dono**, comparando por `card_instance_id` e nunca por `==` entre `BankUnit` (research D8)
- [X] T022 [US5] Criar `server/apps/game/engine/spell_effect.py` com `apply_spell_effect(match, caster, effect, target, *, catalog)` e o despacho `match` **exaustivo** sobre a união `SpellEffect`, terminando sempre em `bury_dead_units`
- [X] T023 [US5] Implementar em `spell_effect.py` os braços `BuffUnitHealth` e `PreventUnitDamage`: `HealthModifier` e `DamageImmunity` no alvo, cada um com `duration=effect.duration` — **nunca um literal** (FR-047)
- [X] T024 [US5] Implementar em `spell_effect.py` o braço `DamageUnit`, delegando a `deal_damage_to_unit`
- [X] T025 [US5] Implementar em `spell_effect.py` os braços `RestoreNexus` e `SacrificeNexusForAttack`, este último aplicando o `AttackModifier` a **todo** o banco do lançador **antes** de `change_nexus(match, caster, -nexus_cost)`, para que a troca seja indivisível qualquer que seja o comportamento da §10
- [X] T026 [US5] Criar `server/apps/game/tests/fake_spell_board.py`: uma partida na Fase de Ação com unidades conhecidas nos dois bancos e os cinco feitiços do MVP nas mãos, no formato de `fake_match_state.py`
- [X] T027 [US5] Acrescentar `apply_spell_effect`, `deal_damage_to_unit`, `bury_dead_units` e as quatro funções de `unit_vitals` ao `__all__` de `server/apps/game/engine/__init__.py`

### Tests for User Story 5

- [X] T028 [P] [US5] Escrever `server/apps/game/tests/test_unit_damage.py` cobrindo vida máxima contra restante, morte no limite exato (dano == máxima), morte por excesso, unidade que sobrevive, e o enterro no cemitério do **dono** com dano e modificadores ficando para trás
- [X] T029 [P] [US5] Acrescentar a `test_unit_damage.py` a imunidade: dano em unidade com `DamageImmunity` ativa não acumula e não mata; e duas cópias intactas da mesma carta no mesmo banco não são removidas juntas quando só uma morre
- [X] T030 [P] [US5] Escrever em `server/apps/game/tests/test_spell_effect.py` os cinco efeitos com os números do catálogo: SHIELD soma 2 à máxima sem tocar o dano, BARRIER dá imunidade até o fim da rodada, FIRE tira 8 e dá +3 a todas as unidades do lançador (e só dele), POTION soma 5, AX soma 3 de dano
- [X] T031 [US5] Acrescentar a `test_spell_effect.py` os casos de borda: FIRE sem nenhuma unidade em campo cobra os 8 mesmo assim; POTION com 20 de Nexus leva a 25; buff de vida em unidade danificada sobe a máxima e não muda o dano; buff que salva uma unidade cujo dano igualaria a vida do molde

**Checkpoint**: US5 completa. Os cinco efeitos são executáveis e testáveis sem pilha nenhuma.

---

## Phase 5: User Story 6 - Aplicar efeito e empilhar são coisas separadas (Priority: P1)

**Goal**: garantir que o aplicador não sabe de qual caminho a chamada veio, para
que a feature de combate não precise de uma segunda implementação de cada
efeito.

**Independent Test**: aplicar cada um dos cinco efeitos direto, sem pilha, e
conferir que o resultado é o mesmo que a Fase 9 vai produzir pela pilha, a
partir do mesmo estado inicial.

**Nota**: esta fase quase não tem produção. O que ela entrega é a **prova** de
uma propriedade que a Fase 4 já construiu — e é a prova que impede a feature de
combate de divergir.

### Implementation for User Story 6

- [X] T032 [US6] Revisar a assinatura de `apply_spell_effect` em `server/apps/game/engine/spell_effect.py` e confirmar que nenhum parâmetro, campo ou global informa a origem da chamada; ajustar o docstring para nomear as duas origens previstas (pilha da §6 e feitiço imediato da §7.2)

### Tests for User Story 6

- [X] T033 [P] [US6] Acrescentar a `server/apps/game/tests/test_spell_effect.py` a afirmação de que cada efeito é executado em exatamente um lugar do código, exercitando os cinco pelo aplicador e nenhum por caminho alternativo
- [X] T034 [US6] Acrescentar a `test_spell_effect.py` o teste de exaustividade da união: um `match` sobre `SpellEffect` cobre os cinco braços, e a revalidação de alvo **não** acontece dentro do aplicador — ele recebe o `BankUnit` já resolvido

**Checkpoint**: US6 completa. A fronteira que mantém a feature de combate pequena está afirmada por teste.

---

## Phase 6: User Story 1 - Lançar um feitiço (Priority: P1) 🎯 MVP

**Goal**: a terceira ação da Fase de Ação. Desconta energia, tira a carta da
mão, põe o feitiço no topo da pilha — **sem aplicar o efeito**.

**Independent Test**: com 5 de energia, um feitiço de custo 5 na mão e uma
unidade aliada no banco, lançar mirando a unidade e conferir energia em 0, mão
com uma carta a menos, pilha com uma entrada, nenhuma alteração em vida, ataque,
Nexus ou cemitério, passes em 0 e prioridade no oponente.

### Implementation for User Story 1

- [X] T035 [US1] Acrescentar `ActionKind.CAST_SPELL` e o braço `CastSpellAction` (`actor_user_id`, `card_instance_id`, `target_card_instance_id: CardInstanceId | None = None`) a `server/apps/game/engine/player_action.py`, e estender a união `PlayerAction`, conforme [contracts/cast_spell.md](./contracts/cast_spell.md) §1
- [X] T036 [US1] Criar `server/apps/game/engine/cast_spell.py` com `cast_spell(match, actor, action, *, catalog)` e a guarda `_as_spell`, levantando `CardIsNotASpellError` — simétrica de `CardIsNotAUnitError`
- [X] T037 [US1] Implementar em `cast_spell.py` a validação de alvo pela tabela de decisão de [contracts/cast_spell.md](./contracts/cast_spell.md) §6, lendo `effect.target_kind` do catálogo e **nunca** a descrição em português da carta
- [X] T038 [US1] Implementar em `cast_spell.py` o efeito da jogada aceita, nesta ordem e só depois das quatro guardas: desconta a energia, `hand.remove`, `stack.append(StackEntry(...))` com o identificador do alvo, e `consecutive_passes = 0`
- [X] T039 [US1] Acrescentar o braço `case CastSpellAction()` a `_apply_action` em `server/apps/game/engine/round_cycle.py`, delegando a `cast_spell`
- [X] T040 [US1] Acrescentar `CastSpellAction` e `CardIsNotASpellError` ao `__all__` de `server/apps/game/engine/__init__.py` — **`cast_spell` não é exportada**, pela mesma razão que `run_upkeep` e `end_round` não são

### Tests for User Story 1

- [X] T041 [US1] Escrever `server/apps/game/tests/test_cast_spell.py` cobrindo o lançamento aceito: energia descontada, carta fora da mão, entrada no topo da pilha com o identificador do alvo e o lançador, passes em 0, prioridade no oponente, energia exatamente igual ao custo aceita, e — lendo o estado inteiro — **nenhum** Nexus, modificador, dano ou cemitério alterado

**Checkpoint**: US1 completa. Um jogador consegue pôr um feitiço na pilha, e a pilha deixa de estar sempre vazia.

---

## Phase 7: User Story 8 - Recusas de lançamento que nomeiam o ofensor (Priority: P1)

**Goal**: toda jogada ilegal é recusada citando o valor ofensor, com a guarda
que falhou distinguível por classe, e o estado idêntico campo a campo.

**Independent Test**: para cada caso de recusa, tirar uma foto do estado com
`match_snapshot`, tentar o lançamento, e comparar; e conferir que a mensagem cita
o valor ofensor.

### Implementation for User Story 8

- [X] T042 [US8] Acrescentar a `server/apps/game/engine/cast_spell.py` as recusas `SpellTakesNoTargetError` e `SpellNeedsTargetError`, esta citando o `TargetKind` esperado, conforme [contracts/cast_spell.md](./contracts/cast_spell.md) §5
- [X] T043 [US8] Acrescentar a `cast_spell.py` as recusas `WrongSpellTargetSideError` — citando o alvo, o `TargetKind` esperado e de quem é o banco — e `SpellTargetNotOnBattlefieldError`, distinguindo as duas por uma consulta a `match.bank_unit()` depois de varrer o banco esperado
- [X] T044 [US8] Acrescentar as quatro recusas de alvo ao `__all__` de `server/apps/game/engine/__init__.py`

### Tests for User Story 8

- [X] T045 [P] [US8] Acrescentar a `server/apps/game/tests/test_cast_spell.py` as recusas de alvo: feitiço sem alvo recebendo um, feitiço com alvo lançado sem, alvo aliado mirando o banco do oponente, alvo inimigo mirando o próprio banco, e alvo que não está em banco nenhum
- [X] T046 [P] [US8] Acrescentar a `test_cast_spell.py` as recusas de carta e recurso: energia insuficiente citando custo e disponível, carta que não está na mão, carta de unidade na ação de lançar feitiço, e carta do oponente
- [X] T047 [US8] Acrescentar a `test_cast_spell.py` a ordem das guardas: sem prioridade **e** com alvo errado **e** sem energia, a recusa é a de prioridade; e fora da Fase de Ação, a recusa é a de fase
- [X] T048 [US8] Acrescentar a `test_cast_spell.py` a atomicidade: em **todos** os casos de recusa, `match_snapshot` antes e depois é idêntico, a pilha está como estava, e nem `next_card_instance_id` nem `next_roll_ordinal` avançaram

**Checkpoint**: US8 completa. Toda recusa de lançamento nomeia o ofensor e não muda nada.

---

## Phase 8: User Story 2 - Responder no topo (Priority: P1)

**Goal**: o oponente responde no topo da pilha, e a pilha guarda a ordem de
lançamento e o lançador de cada entrada.

**Independent Test**: A lança um feitiço, B responde, e conferir que a pilha tem
duas entradas na ordem de lançamento, com a de B no topo e o `caster_user_id`
correto em cada uma.

**Nota**: **nenhuma tarefa de produção.** A prioridade troca depois de toda ação
desde a feature 005, e a pilha aceita duas entradas porque é uma lista. O que
esta fase entrega é a afirmação — e a ordem LIFO e o `caster_user_id` são
exatamente o que a Fase 9 vai consumir.

### Tests for User Story 2

- [X] T049 [P] [US2] Escrever `server/apps/game/tests/test_stack_resolution.py` com os casos de empilhamento: A lança e B responde, a pilha tem duas entradas com a de B no topo, cada uma registrando o `user_id` de quem a lançou
- [X] T050 [P] [US2] Acrescentar a `test_stack_resolution.py` três feitiços alternados, conferindo que a ordem preserva o lançamento; e a recusa de quem responde sem prioridade, deixando a pilha como estava
- [X] T051 [US2] Acrescentar a `test_stack_resolution.py` o caso de jogar unidade com a pilha não vazia: a jogada é aceita, os passes zeram e a pilha continua intacta — jogar unidade não usa a pilha e não a resolve

**Checkpoint**: US2 completa. A pilha comporta feitiços dos dois jogadores, na ordem certa.

---

## Phase 9: User Story 3 - Resolver a pilha inteira em LIFO (Priority: P1)

**Goal**: os dois passes com a pilha não vazia resolvem a pilha inteira, do topo
para a base, sem prioridade entre um feitiço e o seguinte, e devolvem a partida
à Fase de Ação com a prioridade de quem **abriu** a pilha.

**Independent Test**: com dois feitiços de jogadores diferentes na pilha, fazer
os dois passarem e conferir, numa única leitura do resultado, que a pilha está
vazia, que as cartas estão nos cemitérios dos respectivos lançadores, que os
efeitos foram aplicados na ordem inversa do lançamento, que os passes estão em 0,
que a prioridade é de quem lançou o mais antigo, e que a rodada é a mesma.

### Implementation for User Story 3

- [X] T052 [US3] Criar `server/apps/game/engine/stack_resolution.py` com `resolve_stack(match, *, catalog)`: lê o iniciador em `match.stack[0].caster_user_id` **antes** do laço, drena com `while match.stack`, e termina em `_reopen_action_phase`, conforme [contracts/stack_resolution.md](./contracts/stack_resolution.md) §2
- [X] T053 [US3] Implementar `_resolve_top` em `stack_resolution.py`: `pop` antes de qualquer decisão, e a carta ao cemitério do **lançador** depois de todos os caminhos
- [X] T054 [US3] Implementar `_apply_while_the_match_is_live` em `stack_resolution.py`: não aplica nada se `match.is_over`; revalida o alvo com `match.bank_unit()` e trata `None` como **fizzle**; feitiço sem alvo nunca fizzla
- [X] T055 [US3] Implementar em `stack_resolution.py` o estreitamento do molde para `Spell` com `isinstance`, levantando `CardIsNotASpellError` no braço impossível — nunca `assert`, que some com `-O`, nem `cast`
- [X] T056 [US3] Implementar `_reopen_action_phase` em `stack_resolution.py`: `return` cedo se a partida acabou; senão zera os passes, põe a prioridade no iniciador e a fase em `ACTION`. A rodada **não** fecha
- [X] T057 [US3] Escrever em `server/apps/game/tests/test_stack_resolution.py` a resolução chamada **direto** sobre uma pilha montada à mão, antes de a cascata conhecê-la: LIFO, fizzle por alvo ausente, cemitério do lançador, prioridade no iniciador, rodada inalterada
- [X] T058 [US3] Acrescentar `MatchPhase.STACK_RESOLUTION` a `_AUTOMATIC_PHASES` e o braço correspondente a `_run_automatic_phase` em `server/apps/game/engine/round_cycle.py`, passando `catalog` por `_settle`; remover o comentário que explicava a ausência da fase e atualizar os docstrings de `_settle` e `_exit_action_phase`

### Tests for User Story 3

- [X] T059 [US3] Acrescentar a `test_stack_resolution.py` a resolução pela cascata: dois passes com a pilha não vazia devolvem a partida na Fase de Ação com a pilha vazia, numa única resposta, sem que o chamador observe `STACK_RESOLUTION`
- [X] T060 [P] [US3] Acrescentar a `test_stack_resolution.py` a prioridade: A lança, B responde, e depois da resolução a prioridade é de **A**; e o caso em que o mesmo jogador lançou os dois, em que ela volta para ele
- [X] T061 [US3] Acrescentar a `test_stack_resolution.py` a continuidade da rodada: depois de resolver, os dois passam de novo e **aí sim** a rodada fecha; e que a resolução não alterou energia nem fez ninguém comprar carta

**Checkpoint**: US3 completa. A pilha resolve e a partida volta a girar. É o primeiro ponto em que a feature funciona de ponta a ponta.

---

## Phase 10: User Story 4 - O exemplo canônico da §6 (Priority: P1)

**Goal**: o exemplo que a nota de domínio escreve funciona exatamente como
escrito — o dano resolve primeiro, X morre, e o buff fizzla porque X não existe
mais.

**Independent Test**: montar exatamente o cenário do exemplo, executar os dois
passes, e conferir que X está no cemitério do dono, que o buff não deixou
modificador em lugar nenhum, e que as duas cartas de feitiço estão nos
cemitérios dos respectivos lançadores.

**Nota**: nenhuma tarefa de produção. Este é o teste que prova que a
revalidação por identificador é real, e não uma referência disfarçada. Se falhar,
a pilha está aplicando efeito em unidade removida do jogo.

### Tests for User Story 4

- [X] T062 [US4] Acrescentar a `server/apps/game/tests/test_stack_resolution.py` o exemplo canônico da §6 completo: buff de vida em X por A, dano em X por B, os dois passam, e as três afirmações — X no cemitério do dono, buff sem modificador nenhum, as duas cartas nos cemitérios dos lançadores
- [X] T063 [P] [US4] Acrescentar o caso de dois feitiços de dano mirando a mesma unidade, o de cima já bastando para matá-la: o de baixo fizzla
- [X] T064 [P] [US4] Acrescentar o caso em que a unidade **sobrevive** ao feitiço de cima: o de baixo **não** fizzla e o efeito é aplicado
- [X] T065 [US4] Acrescentar o caso do alvo protegido por MAGIC BARRIER: o dano não entra, a unidade não morre, e o feitiço **não** fizzla — o alvo estava em campo e o efeito foi aplicado

**Checkpoint**: US4 completa. O fizzle é real e a morte é verificada assim que o efeito termina.

---

## Phase 11: User Story 9 - Não quebrar 001, 002 e 005 (Priority: P2)

**Goal**: todo estado que esta feature produz sobrevive à ida e à volta pelo
Redis, e as suítes das três features anteriores passam sem alteração nenhuma.

**Independent Test**: rodar as suítes das features 001, 002 e 005 sem tocar em
nenhum arquivo de teste delas, e conferir que passam.

### Tests for User Story 9

- [X] T066 [US9] Acrescentar a `server/apps/game/tests/test_spell_state_round_trip.py` o estado cheio: pilha com feitiços dos dois jogadores, unidades com os três tipos de modificador, dano acumulado e cemitérios povoados, indo e voltando pelo documento com igualdade campo a campo
- [X] T067 [P] [US9] Acrescentar a `test_spell_state_round_trip.py` a prova da §8: um `DamageImmunity` criado por MAGIC BARRIER é removido no Fim de Rodada, e um `HealthModifier` e um `AttackModifier` permanentes sobrevivem — pela **mesma** varredura que a feature 005 entregou, sem alteração em `round_end.py`
- [X] T068 [P] [US9] Acrescentar a `test_spell_state_round_trip.py` a afirmação de que nenhuma decisão de regra desta feature lê `Spell.description`: o tipo de alvo e a duração vêm dos campos estruturados do catálogo
- [X] T069 [US9] Rodar `cd server && pytest` inteiro e confirmar contra a contagem de T001 que nenhum teste existente foi alterado, removido ou passou a falhar

**Checkpoint**: US9 completa. As três features anteriores continuam íntegras.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: os textos que deixam de ser previsão e viram fato, e as portas de
qualidade.

- [X] T070 [P] Reescrever o docstring do pacote em `server/apps/game/engine/__init__.py`: a §6 entrou, a lista de pendências encolhe para o combate da §7
- [X] T071 [P] Reescrever o comentário da união `SpellEffect` em `server/apps/game/cards/effects.py`, que previa "quando a pilha de feitiços for implementada", para apontar `engine/spell_effect.py` como o `match` que ele antecipava
- [X] T072 [P] Revisar os docstrings de `Match.bank_unit`, `StackEntry`, `BankUnit.damage_taken` e do módulo `match/modifiers.py` e confirmar que **não** mudaram — eles previam esta feature corretamente, e a tarefa é verificar, não editar
- [X] T073 Rodar `cd server && black server/` e `cd server && mypy`, confirmando strict verde sem nenhuma relaxação nova em `mypy.ini`
- [X] T074 Percorrer o [quickstart.md](./quickstart.md) inteiro no shell, incluindo o exemplo canônico da §6 e o Nexus em zero, e conferir que cada valor lido bate com o documentado
- [X] T075 Conferir a checklist de tamanho: nenhum arquivo acima de 500 linhas, nenhuma função acima de 20, no máximo 2 níveis de indentação — com atenção a `player_action.py`, que é o maior depois desta feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Fase 1 (Setup)**: sem dependência.
- **Fase 2 (Foundational)**: depende da Fase 1. **Bloqueia todas as histórias** —
  `victory.py` grava o tipo que ela define, e `cast_spell.py` usa as guardas que
  ela move de casa.
- **Fase 3 (US7)**: depende da Fase 2.
- **Fase 4 (US5)**: depende da Fase 3 — dois dos cinco efeitos chamam
  `change_nexus`.
- **Fase 5 (US6)**: depende da Fase 4 — é a prova de uma propriedade do que ela
  construiu.
- **Fase 6 (US1)**: depende só da Fase 2. **Pode correr em paralelo com as Fases
  3, 4 e 5** — arquivos diferentes, e empilhar não depende de aplicar.
- **Fase 7 (US8)**: depende da Fase 6 (mesmo módulo).
- **Fase 8 (US2)**: depende da Fase 6.
- **Fase 9 (US3)**: depende das Fases 6 **e** 4 — drena o que o lançamento
  empilhou e chama o que os efeitos escreveram.
- **Fase 10 (US4)**: depende da Fase 9.
- **Fase 11 (US9)**: depende de todas as anteriores.
- **Fase 12 (Polish)**: depende de tudo.

### O único caminho crítico

```
Fase 2 ──> Fase 3 (US7) ──> Fase 4 (US5) ──┐
   │                                        ├──> Fase 9 (US3) ──> Fase 10 (US4)
   └──────> Fase 6 (US1) ──────────────────┘
```

As Fases 5, 7 e 8 saem desse caminho e podem ser feitas a qualquer momento
depois das suas dependências.

### Within Each User Story

- Implementação antes dos testes, como nas features anteriores deste projeto:
  os contratos já estão escritos em `contracts/`, e o teste afirma o contrato,
  não o descobre.
- Tipos antes das regras que os gravam.
- Consultas (`unit_vitals`) antes das mutações (`unit_damage`) antes do
  despacho (`spell_effect`).
- A regra testável sozinha antes da cascata que a atravessa (T057 antes de
  T058).

### Parallel Opportunities

- **T002 e T003** — o tipo e o teste dele, arquivos diferentes.
- **T006** roda em paralelo com T005 se `MatchOutcomeDocument` já existir.
- **T016, T017, T018** — três blocos de teste no mesmo arquivo; paralelos se
  escritos como funções independentes.
- **T020 e T028**, **T028 e T029**, **T030 e T031** — vitais e dano em arquivos
  diferentes.
- **Fases 3–5 e Fase 6** correm em paralelo por completo: `victory.py`,
  `unit_*.py` e `spell_effect.py` de um lado, `cast_spell.py` e
  `player_action.py` do outro. É a maior oportunidade da feature.
- **T045 e T046** — dois blocos de recusa, sem dependência entre si.
- **T063, T064** — dois cenários de fizzle independentes.
- **T070, T071, T072** — três arquivos diferentes no polimento.

---

## Parallel Example: depois da Fase 2

```bash
# Duas frentes, sem conflito de arquivo:

# Frente A -- o que aplica (Fases 3, 4, 5)
Task: "T012 Criar engine/victory.py com check_victory e _finish_match"
Task: "T020 Criar engine/unit_vitals.py com as quatro consultas"
Task: "T021 Criar engine/unit_damage.py com dano e enterro"

# Frente B -- o que empilha (Fases 6, 7)
Task: "T035 Acrescentar CastSpellAction a engine/player_action.py"
Task: "T036 Criar engine/cast_spell.py com cast_spell e _as_spell"
```

As duas frentes só se encontram em `engine/__init__.py` (T015, T027, T040, T044)
e na Fase 9, que consome as duas.

---

## Implementation Strategy

### MVP

A Fase 6 (US1) é a primeira coisa que um jogador consegue fazer, e é onde o 🎯
está. Mas ela sozinha entrega **um feitiço que nunca resolve** — é MVP de
formato, não de jogo.

### Parada útil

A primeira parada em que a feature vale alguma coisa é o **fim da Fase 9**:
lançar, responder, os dois passarem, a pilha resolver inteira e os cinco efeitos
acontecerem. Antes disso a pilha é um depósito, e depois disso a Fase 10 só
prova que o fizzle é real.

Uma segunda parada defensável é o **fim da Fase 5**: os cinco efeitos existem e
são aplicáveis direto, o que já entrega à feature de combate tudo o que FR-064
promete a ela — mesmo sem pilha nenhuma.

### Entrega incremental

1. Fases 1–2 → o desfecho é um tipo gravável, a suíte antiga intacta
2. Fase 3 → a §10 executável
3. Fases 4–5 → os cinco efeitos, aplicáveis direto
4. Fases 6–8 → a pilha enche, e recusa o que precisa recusar
5. **Fase 9 → a pilha resolve. Parada útil.**
6. Fase 10 → o fizzle provado pelo exemplo da nota
7. Fase 11 → as features anteriores conferidas
8. Fase 12 → os textos e as portas de qualidade

### Parallel Team Strategy

Com dois desenvolvedores, depois da Fase 2:

- **A** faz as Fases 3, 4 e 5 — vitória e efeitos
- **B** faz as Fases 6, 7 e 8 — lançamento e recusas
- Os dois se encontram na Fase 9, que precisa das duas frentes

Com três, o terceiro pega a Fase 11 desde cedo: o teste de round-trip do estado
terminal (T008) já é escrevível ao fim da Fase 2.

---

## Notes

- `[P]` = arquivo diferente, sem dependência pendente
- `[Story]` mapeia a tarefa para a história, para rastreabilidade
- Toda tarefa cita o arquivo exato; nenhuma cita "vários arquivos"
- Commit por tarefa ou por grupo lógico; a suíte fica verde em todo checkpoint
- **T005 e T010 são atômicas** — dividi-las derruba a suíte inteira, não um
  arquivo
- **T057 vem antes de T058** — a resolução testada antes de a cascata entrar
  nela; na ordem contrária existe um commit em que `_settle` gira para sempre
- Nenhum arquivo de teste das features 001, 002 e 005 é alterado. Se um deles
  precisar mudar, é sinal de que o desenho divergiu do plano — pare e releia
  research [D15](./research.md)
