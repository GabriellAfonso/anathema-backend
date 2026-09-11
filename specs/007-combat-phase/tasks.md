---

description: "Task list for 007-combat-phase"
---

# Tasks: Combate

**Input**: Design documents from `specs/007-combat-phase/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/declare_attack.md](./contracts/declare_attack.md),
[contracts/defense_window.md](./contracts/defense_window.md),
[contracts/combat_resolution.md](./contracts/combat_resolution.md),
[quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. Não é preferência de estilo — o princípio V
da constituição exige teste para toda função nova, e o quickstart põe `pytest`
como porta de conclusão.

**Organization**: agrupadas por história de usuário, na ordem que as dependências
permitem. Onde a ordem diverge da numeração da spec, a razão está escrita abaixo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a que história pertence (US1 a US8)
- Todo caminho de arquivo é relativo à raiz do repositório

## Estratégia de corte

Esta feature acrescenta estado ao `match/` — o segundo acréscimo desde a feature
002 —, cinco braços à união de ações e um `return` na função que troca a
prioridade. A suíte precisa ficar verde em todo checkpoint de fase, e para isso
seis edições precisam ser atômicas.

- **T008 — a chave nova no `MatchDocument`.** Acrescentar o campo em
  `documents.py` sem escrever a ida e a volta em `serialization.py` deixa o
  `TypedDict` com uma chave que `to_match_document` não produz, e o mypy strict
  reprova o dicionário literal. As duas edições são a mesma tarefa. É o mesmo
  corte que a feature 006 fez com `outcome`.
- **T012 — `keeps_priority`.** Declarar a `ClassVar` nos três braços existentes e
  ler `action.keeps_priority` em `_pass_priority` são a mesma edição. A
  declaração sem a leitura é campo morto; a leitura sem a declaração não
  compila. Com os três braços declarando `False`, nada muda de comportamento — e
  é isso que a suíte verde nesta tarefa prova.
- **T015, T022, T038, T046 — cada braço novo com o `case` dele.** O `match` de
  `_apply_action` fecha com `assert_never`, então um braço na união sem `case`
  correspondente é erro de mypy. Acrescentar o braço, o `case` e o `__all__` são
  a mesma edição; separá-los derruba a checagem inteira, não um arquivo.
- **T043 — a mudança de casa das guardas de feitiço.** Criar
  `spell_cast_guards.py`, mover as cinco recusas, passar `cast_spell.py` a usar a
  porta nova, corrigir o import de `stack_resolution.py` e ajustar o `__all__`
  são a mesma edição. Separá-las deixa `engine/__init__.py` importando um nome
  que não existe, e isso derruba a suíte inteira. É o mesmo corte que a feature
  006 fez com `card_in_hand` (research [D10](./research.md)).

### Por que a ordem diverge da numeração da spec

A spec numera as histórias na ordem em que o jogador as vive: declarar,
bloquear, conjurar, apanhar, limpar. A ordem de construção troca a terceira pela
quarta, porque **o feitiço imediato não é pré-requisito de nada** e o dano é
pré-requisito da limpeza.

| Fase | História | Depende de | Por quê |
|---|---|---|---|
| 2 | — | — | O `CombatState` não é história nenhuma; é o estado que a §7.1 grava e a §7.3 lê. |
| 3 | US1 | Fase 2 | Sem declaração não existe combate em que bloquear. |
| 4 | US2 | US1 | O pareamento precisa de atacantes declarados. |
| 5 | US4 | US2 | O dano lê o pareamento. É testável direto, sobre um estado montado, **antes** de existir a ação que o dispara — o mesmo corte que a feature 006 fez com `resolve_stack`. |
| 6 | US5 | US4 | A limpeza chama o dano. |
| 7 | US3 | US1 (+ US5 para os cenários de integração) | O feitiço imediato só precisa da fase `COMBAT` existir. **Corre em paralelo com as Fases 4, 5 e 6.** |
| 8 | US6 | US5 | "A rodada continua" é uma propriedade do que a limpeza devolveu. |
| 9 | US7 | Fase 2 | O round-trip já é escrevível depois de T008. Fica aqui por arrumação, não por dependência. |
| 10 | US8 | tudo | A partida inteira precisa de todas as peças. |

---

## Phase 1: Setup

**Purpose**: conferir o ponto de partida e os números que os testes vão medir.

- [X] T001 Rodar `cd server && pytest && mypy && black --check .` e confirmar as três portas verdes antes de qualquer edição
- [X] T002 [P] Conferir em `server/apps/game/cards/mvp_catalog.py` os pares (ataque, vida) das cinco unidades que os testes usam — DARK AGE 3/2, KHRAS 2/4, SKILLET 4/5, POLAROID 2/6, MORTEM 7/2 — e corrigir [quickstart.md](./quickstart.md) se algum divergir
- [X] T003 [P] Confirmar a previsão D20 lendo os cinco inventários que poderiam quebrar: `test_the_phase_set_is_closed` em `server/apps/game/tests/test_match_state.py`, `test_each_action_declares_its_own_kind` e `test_both_actions_of_this_feature_belong_to_the_action_phase` em `server/apps/game/tests/test_player_action.py`, `test_the_shared_round_fields_appear` em `server/apps/game/tests/test_player_view.py`, e as afirmações de chave em `server/apps/game/tests/test_match_serialization.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: o estado de combate, a forma gravada e o mecanismo da prioridade
que não troca.

**⚠️ CRITICAL**: nenhuma história começa antes desta fase fechar. Todas as cinco
regras do combate leem `Match.combat`, e todas as quatro ações da janela leem
`keeps_priority`.

- [X] T004 Criar `server/apps/game/match/combat_state.py` com `BlockAssignment`, `CombatState` e as três consultas `is_attacking`, `blocker_of` e `attacker_blocked_by`, seguindo [data-model.md §1](./data-model.md)
- [X] T005 [P] Criar `server/apps/game/tests/test_combat_state.py` com os testes das três consultas, incluindo o `None` para o atacante sem bloqueador e para o bloqueador não atribuído
- [X] T006 Acrescentar `combat: CombatState | None = None`, o método `ongoing_combat()` e a recusa `MatchIsNotInCombatError` a `server/apps/game/match/match_state.py`, e reescrever o docstring de `MatchPhase` para dizer o que `COMBAT` passou a ser
- [X] T007 Acrescentar a `server/apps/game/tests/test_combat_state.py` os testes de `ongoing_combat()`: devolve o estado dentro do combate, e recusa citando a fase fora dele
- [X] T008 **ATÔMICA** Acrescentar `BlockAssignmentDocument`, `CombatDocument` e a chave `combat` a `server/apps/game/match/documents.py` **e**, na mesma edição, as quatro funções de ida e volta a `server/apps/game/match/serialization.py`
- [X] T009 [P] Acrescentar a chave `combat` a `PlayerView` e a `build_player_view` em `server/apps/game/match/player_view.py`
- [X] T010 Acrescentar `CombatState`, `BlockAssignment`, `CombatDocument`, `BlockAssignmentDocument` e `MatchIsNotInCombatError` ao `__all__` de `server/apps/game/match/__init__.py`
- [X] T011 [P] Criar `server/apps/game/tests/fake_combat_board.py` no formato de `fake_spell_board.py`, com uma partida em Fase de Ação, token no primeiro jogador, pilha vazia e as cinco unidades do T002 posicionáveis nos dois bancos
- [X] T012 **ATÔMICA** Declarar `keeps_priority: ClassVar[bool] = False` em `PlayUnitAction`, `CastSpellAction` e `PassAction` em `server/apps/game/engine/player_action.py` **e**, na mesma edição, pôr o `return` correspondente em `_pass_priority` de `server/apps/game/engine/round_cycle.py`, com o comentário que explica por que a exceção mora na ação

**Checkpoint**: `pytest`, `mypy` e `black --check` verdes, e **nenhum
comportamento diferente** — `test_action_phase.py` passa sem alteração, que é a
prova de que T012 não vazou.

---

## Phase 3: User Story 1 - Declarar ataque (Priority: P1) 🎯 MVP de formato

**Goal**: a quarta e última ação da Fase de Ação consome o token, registra os
atacantes e põe a partida em Combate com a prioridade no defensor.

**Independent Test**: com o token, a pilha vazia e três unidades no banco,
declarar ataque com duas delas e conferir token consumido, fase em Combate,
prioridade no defensor, as duas unidades registradas, e nenhuma energia, carta,
Nexus ou dano alterado.

- [X] T013 [US1] Criar `server/apps/game/engine/declare_attack.py` com as sete recusas de [contracts/declare_attack.md](./contracts/declare_attack.md): `NotTheTokenHolderError`, `AttackTokenAlreadyConsumedError`, `StackIsNotEmptyError`, `BankHasNoUnitsError`, `NoAttackersSelectedError`, `AttackerNotInBankError` e `DuplicateAttackerError`, cada uma citando o valor ofensor
- [X] T014 [US1] Acrescentar a `server/apps/game/engine/declare_attack.py` a função `declare_attack`, as seis guardas na ordem do contrato e o privado `_enter_combat`, único ponto do módulo que escreve o par `(combat, phase)`
- [X] T015 [US1] **ATÔMICA** Acrescentar `ActionKind.DECLARE_ATTACK` e `DeclareAttackAction` a `server/apps/game/engine/player_action.py`, o `case DeclareAttackAction()` a `_apply_action` em `server/apps/game/engine/round_cycle.py` e os nomes ao `__all__` de `server/apps/game/engine/__init__.py`
- [X] T016 [P] [US1] Criar `server/apps/game/tests/test_declare_attack.py` com o caminho aceito — cenários 1 a 4 da US1: um atacante, dois, todos os seis, e o estado inteiro intocado fora dos quatro campos que a ação escreve
- [X] T017 [P] [US1] Acrescentar a `server/apps/game/tests/test_declare_attack.py` as sete recusas — cenários 5 a 11 da US1 —, cada uma conferindo que a mensagem cita o valor ofensor
- [X] T018 [US1] Acrescentar a `server/apps/game/tests/test_declare_attack.py` a atomicidade das sete recusas com `match_snapshot`, conferindo que os dois contadores da partida também não avançaram
- [X] T019 [US1] Acrescentar a `server/apps/game/tests/test_declare_attack.py` o teste da cascata: `submit_action` devolve a partida **em Combate**, com a prioridade no defensor e os passes em 0, e não em `ROUND_END` nem em `STACK_RESOLUTION` mesmo com o oponente tendo passado uma vez antes

**Checkpoint**: a partida chega a `MatchPhase.COMBAT` pela primeira vez desde a
feature 002. Não há o que fazer lá dentro ainda.

---

## Phase 4: User Story 2 - A janela livre do defensor (Priority: P1)

**Goal**: o defensor atribui e remove bloqueadores quantas vezes quiser, com o
pareamento 1:1 estrito, e **sem que a prioridade saia dele**.

**Independent Test**: com dois atacantes declarados e duas unidades no banco do
defensor, atribuir, atribuir, remover e reatribuir — quatro ações seguidas — e
conferir que a prioridade continuou no defensor nas quatro e que o pareamento
final é o esperado.

- [X] T020 [US2] Criar `server/apps/game/engine/blocker_pairing.py` com as cinco recusas de [contracts/defense_window.md §3](./contracts/defense_window.md): `BlockerNotInBankError`, `UnitIsNotAttackingError`, `BlockerAlreadyBlockingError`, `AttackerAlreadyBlockedError` e `BlockerNotAssignedError`
- [X] T021 [US2] Acrescentar a `server/apps/game/engine/blocker_pairing.py` as funções `assign_blocker` e `remove_blocker`, com as quatro guardas da primeira na ordem do contrato e a guarda única da segunda
- [X] T022 [US2] **ATÔMICA** Acrescentar `ASSIGN_BLOCKER`, `REMOVE_BLOCKER`, `AssignBlockerAction` e `RemoveBlockerAction` — com `allowed_phases = {COMBAT}` e `keeps_priority = True` — a `server/apps/game/engine/player_action.py`, os dois `case` a `_apply_action` em `server/apps/game/engine/round_cycle.py` e os nomes ao `__all__` de `server/apps/game/engine/__init__.py`
- [X] T023 [P] [US2] Criar `server/apps/game/tests/test_blocker_pairing.py` com atribuir e remover aceitos — cenários 1 a 4 da US2 —, conferindo o conteúdo de `combat.blocks` depois de cada um
- [X] T024 [P] [US2] Acrescentar a `server/apps/game/tests/test_blocker_pairing.py` as cinco recusas — cenários 5 a 9 da US2 —, com `match_snapshot` provando que nenhuma delas mudou nada
- [X] T025 [US2] Acrescentar a `server/apps/game/tests/test_blocker_pairing.py` o teste de SC-003 — quatro ações seguidas do defensor sem que a prioridade saia dele — e a afirmação de que os quatro braços da §5 declaram `keeps_priority is False`
- [X] T026 [US2] Acrescentar a `server/apps/game/tests/test_blocker_pairing.py` os dois lados de FR-022 a FR-024: o atacante recusado com `NotYourPriorityError` em toda ação, e o defensor recusado com `PhaseForbidsActionError` ao tentar jogar unidade, lançar feitiço pela pilha, passar ou declarar ataque

**Checkpoint**: a janela funciona, o pareamento existe e a alternância da §5
continua intacta fora dela. Ninguém apanha ainda.

---

## Phase 5: User Story 4 - Dano simultâneo (Priority: P1)

**Goal**: o cálculo da §7.3 inteiro — pares, Nexus, imunidade, órfão — com a §10
apurada **uma vez**, depois de os dois Nexus serem alterados.

**Independent Test**: dois atacantes, um bloqueado por uma unidade de força igual
e outro livre, chamar `resolve_combat_damage` sobre um estado montado e conferir
que atacante e bloqueador acumularam o dano um do outro, que o livre levou o
ataque dele ao Nexus do defensor, e que nada chegou ao Nexus pelo par bloqueado.

> `resolve_combat_damage` é testada **direto**, antes de existir a ação que a
> dispara — o mesmo corte que a feature 006 fez com `resolve_stack`.

- [X] T027 [US4] Acrescentar `unit_effective_attack` a `server/apps/game/engine/unit_vitals.py`, com piso em 0, e reescrever os dois parágrafos do docstring do módulo que diziam que ela "não mora aqui ainda"
- [X] T028 [P] [US4] Criar `server/apps/game/tests/test_combat_damage.py` com os testes de `unit_effective_attack`: molde puro, molde mais bônus de SACRIFICIAL FIRE, e o piso em 0 com modificador negativo
- [X] T029 [US4] Acrescentar `_add_to_nexus` e `change_nexus_simultaneously` a `server/apps/game/engine/victory.py`, reescrevendo `change_nexus` sobre o privado comum para que o módulo continue tendo um ponto só que escreve Nexus
- [X] T030 [P] [US4] Acrescentar a `server/apps/game/tests/test_combat_damage.py` os testes de `change_nexus_simultaneously`: altera todos antes de apurar, apura uma vez só, e dois Nexus em 0 ou menos no mesmo cálculo dão empate com os **dois** entre os derrotados
- [X] T031 [US4] Criar `server/apps/game/engine/combat_damage.py` com `_attacking_player` — estreitando `token_holder_user_id` com recusa nomeada, pelo precedente de `round_end._swap_token` — e `_plan_combat_damage`, que implementa a tabela de quatro linhas de [contracts/combat_resolution.md §3](./contracts/combat_resolution.md) sem escrever nada
- [X] T032 [US4] Acrescentar `resolve_combat_damage` a `server/apps/game/engine/combat_damage.py`, aplicando os golpes planejados e chamando `change_nexus_simultaneously` com os **dois** jogadores, o atacante sempre com 0
- [X] T033 [P] [US4] Acrescentar a `server/apps/game/tests/test_combat_damage.py` os cenários 1 a 3 e 14 da US4: par bloqueado trocando dano, não bloqueado no Nexus, mútua destruição, e o Nexus do atacante intocado
- [X] T034 [P] [US4] Acrescentar a `server/apps/game/tests/test_combat_damage.py` as três linhas de revalidação: bloqueador órfão intacto, atacante fora de campo sem causar dano, e bloqueador fora de campo sem que nada chegue ao Nexus
- [X] T035 [P] [US4] Acrescentar a `server/apps/game/tests/test_combat_damage.py` os cenários 7 a 9 e 11 da US4: atacante imune, bloqueador imune, bônus de ataque contando, e três não bloqueados somando no Nexus com uma apuração só

**Checkpoint**: o dano está correto e testado sobre estados montados. Nada ainda
o dispara por uma ação de jogador.

---

## Phase 6: User Story 5 - Limpeza e volta à Fase de Ação (Priority: P1)

**Goal**: encerrar a janela mata quem tinha de morrer dos dois lados de uma vez,
devolve os sobreviventes, apaga o estado de combate e põe a partida de volta
esperando ação.

**Independent Test**: encerrar a janela de um combate com mortes dos dois lados e
conferir, na mesma resposta, mortos nos cemitérios certos, sobreviventes nos
bancos, `match.combat is None`, passes em 0, prioridade no dono do token e fase
`ACTION`.

- [X] T036 [US5] Criar `server/apps/game/engine/combat_cleanup.py` com `end_combat`, chamando `resolve_combat_damage` e depois `bury_dead_units` — e **sem** uma segunda chamada a `check_victory`, pela razão escrita em [contracts/combat_resolution.md §4](./contracts/combat_resolution.md)
- [X] T037 [US5] Acrescentar `_leave_combat` a `server/apps/game/engine/combat_cleanup.py`, com `combat = None` **antes** do `return` da partida terminada, e a devolução de passes, prioridade e fase depois dele
- [X] T038 [US5] **ATÔMICA** Acrescentar `END_DEFENSE_WINDOW` e `EndDefenseWindowAction` a `server/apps/game/engine/player_action.py`, o `case` a `_apply_action` em `server/apps/game/engine/round_cycle.py` e os nomes ao `__all__` de `server/apps/game/engine/__init__.py`
- [X] T039 [P] [US5] Criar `server/apps/game/tests/test_combat_cleanup.py` com os cenários 1 a 3 e 5 da US5: mortos no cemitério do dono, sobreviventes no banco, dano e modificadores ficando para trás, e `match.combat is None`
- [X] T040 [P] [US5] Acrescentar a `server/apps/game/tests/test_combat_cleanup.py` os cenários 4, 6 e 7 da US5: fase, prioridade e passes; o número da rodada igual ao de antes; e nenhuma energia alterada nem carta comprada
- [X] T041 [US5] Acrescentar a `server/apps/game/tests/test_combat_cleanup.py` os cenários 12 e 13 da US4 mais o 9 da US5: o Nexus do defensor a 0 pelo dano encerra a partida, o estado de combate some, e a partida **não** volta para a Fase de Ação
- [X] T042 [US5] Acrescentar a `server/apps/game/tests/test_combat_cleanup.py` o roteiro 1 do [quickstart.md](./quickstart.md) de ponta a ponta, e o cenário 8 da US5: nenhuma chamada devolve a partida numa fase automática

**Checkpoint**: o combate roda inteiro por ações de jogador, do "atacar" ao
"resolver". A feature já vale alguma coisa aqui.

---

## Phase 7: User Story 3 - Feitiço imediato do defensor (Priority: P1)

**Goal**: o defensor lança feitiço dentro da janela, o efeito acontece na hora,
a pilha continua vazia, e **nenhum dos cinco efeitos ganha uma segunda
implementação**.

**Independent Test**: com o defensor bloqueando um atacante, lançar um feitiço de
dano no atacante e conferir que o efeito já aconteceu, que a pilha continua
vazia, que a prioridade continua no defensor, e que a carta já está no cemitério
dele.

> **Corre em paralelo com as Fases 4, 5 e 6.** Só depende da Fase 3 para ter uma
> fase `COMBAT` em que agir. Os cenários de integração (T050, T051) precisam da
> Fase 6.

- [X] T043 [US3] **ATÔMICA** Criar `server/apps/game/engine/spell_cast_guards.py` com `ValidatedSpellCast` e `validated_spell_cast`, movendo para lá as cinco recusas de `server/apps/game/engine/cast_spell.py`, apagando `_owner_of` em favor de `Match.bank_unit()`, reescrevendo `cast_spell` sobre a porta nova, corrigindo o import de `server/apps/game/engine/stack_resolution.py` e ajustando o `__all__` de `server/apps/game/engine/__init__.py`
- [X] T044 [US3] Rodar `cd server && pytest apps/game/tests/test_cast_spell.py apps/game/tests/test_stack_resolution.py` e confirmar verde **sem uma linha alterada** nos dois arquivos — é a prova de que T043 foi movimento de arquivo e não de comportamento (research [D10](./research.md)); se algum precisar mudar, pare e releia o contrato
- [X] T045 [US3] Criar `server/apps/game/engine/cast_combat_spell.py` com `cast_combat_spell`, pondo a carta no cemitério **depois** de `apply_spell_effect` — a ordem de `stack_resolution._resolve_top`, exigida por SC-008 (research [D11](./research.md))
- [X] T046 [US3] **ATÔMICA** Acrescentar `CAST_COMBAT_SPELL` e `CastCombatSpellAction` a `server/apps/game/engine/player_action.py`, o `case` a `_apply_action` em `server/apps/game/engine/round_cycle.py` e os nomes ao `__all__` de `server/apps/game/engine/__init__.py`
- [X] T047 [P] [US3] Criar `server/apps/game/tests/test_cast_combat_spell.py` com os cenários 1 a 3 da US3: efeito na hora, pilha vazia, carta no cemitério do lançador, prioridade e fase inalteradas, e dois feitiços na mesma janela
- [X] T048 [P] [US3] Acrescentar a `server/apps/game/tests/test_cast_combat_spell.py` os cenários 4, 8 e 9 da US3: energia insuficiente, alvo fora de campo, alvo no banco errado, carta que não está na mão, carta de unidade, e o atacante tentando lançar
- [X] T049 [US3] Acrescentar a `server/apps/game/tests/test_cast_combat_spell.py` o teste de SC-008: a partir do mesmo estado inicial, aplicar cada um dos cinco efeitos pelo caminho da pilha e pelo caminho do combate e comparar os dois `match_snapshot` finais **campo a campo**, ordem de cemitério inclusive
- [X] T050 [US3] Acrescentar a `server/apps/game/tests/test_cast_combat_spell.py` os cenários 5 e 6 da US3 e os roteiros 3 e 4 do [quickstart.md](./quickstart.md): feitiço que mata um atacante deixando o bloqueador órfão, buff que faz o bloqueador sobreviver, e defensor que mata todos os atacantes e resolve sem dano nenhum
- [X] T051 [US3] Acrescentar a `server/apps/game/tests/test_cast_combat_spell.py` o caso de FR-062: SACRIFICIAL FIRE lançado por um defensor com 8 ou menos de Nexus encerra a partida na janela, a ação que encerraria a janela é recusada com `MatchIsOverError`, o dano nunca resolve, e o `CombatState` continua íntegro e serializável

**Checkpoint**: a §7 inteira existe. As três histórias P1 restantes só conferem
o que ela devolveu.

---

## Phase 8: User Story 6 - A rodada continua depois do combate (Priority: P2)

**Goal**: provar que o combate é um sub-estado e não um fim de rodada
disfarçado, e que a exceção da janela não vazou.

**Independent Test**: depois de um combate, jogar uma unidade e lançar um feitiço
vendo a prioridade trocar nas duas, e tentar declarar ataque de novo e ser
recusado.

> **Nenhum código de produção nesta fase.** Se alguma tarefa aqui exigir uma
> linha nova em `engine/`, o desenho divergiu do plano — pare e releia
> research [D6 e D7](./research.md).

- [X] T052 [P] [US6] Acrescentar a `server/apps/game/tests/test_combat_cleanup.py` os cenários 1 e 2 da US6: depois do combate, jogar unidade e lançar feitiço pela pilha, com a prioridade trocando nas duas
- [X] T053 [P] [US6] Acrescentar a `server/apps/game/tests/test_combat_cleanup.py` os cenários 3 e 6 da US6: segundo ataque na mesma rodada recusado com `AttackTokenAlreadyConsumedError`, e o defensor do combate recusado com `NotTheTokenHolderError`
- [X] T054 [US6] Acrescentar a `server/apps/game/tests/test_combat_cleanup.py` os cenários 4 e 5 da US6 e o roteiro 6 do [quickstart.md](./quickstart.md): os dois passam com a pilha vazia, a rodada fecha, o token troca de dono no Fim de Rodada, e o novo dono declara ataque na rodada seguinte

**Checkpoint**: a alternância da §5 está provada intacta dos dois lados do
combate.

---

## Phase 9: User Story 7 - O estado de combate sobrevive ao Redis (Priority: P2)

**Goal**: o pareamento atravessa a forma gravada com igualdade campo a campo, e
a ausência é distinguível de um combate sem bloqueadores.

**Independent Test**: declarar, bloquear, serializar, desserializar, conferir
igualdade — e então encerrar a janela pelo estado reconstruído e obter o mesmo
resultado.

> **Nenhum código de produção nesta fase.** T008 já a entregou; esta fase é a
> prova. Escrevível desde o fim da Fase 2, se houver quem a escreva.

- [X] T055 [P] [US7] Criar `server/apps/game/tests/test_combat_state_round_trip.py` com o cenário 1 da US7: três atacantes voltando na mesma ordem, passando por `json.dumps` e `json.loads` entre a ida e a volta
- [X] T056 [P] [US7] Acrescentar a `server/apps/game/tests/test_combat_state_round_trip.py` o cenário 2 da US7: cada bloqueador continua pareado com o mesmo atacante
- [X] T057 [P] [US7] Acrescentar a `server/apps/game/tests/test_combat_state_round_trip.py` o cenário 3 da US7: partida fora do combate volta com `combat is None`, e a ausência é distinguível de `CombatState(blocks=[])`
- [X] T058 [US7] Acrescentar a `server/apps/game/tests/test_combat_state_round_trip.py` o cenário 4 da US7: partida reconstruída no meio do combate, janela encerrada pelo estado reconstruído, resultado idêntico ao de uma que nunca foi gravada

**Checkpoint**: a garantia de round-trip da feature 002 vale com o pareamento
dentro.

---

## Phase 10: User Story 8 - Uma partida completa, do setup à vitória (Priority: P3)

**Goal**: as sete features costuradas. O Fluxo de Partida implementado de ponta a
ponta.

**Independent Test**: montar uma partida pelo setup, alternar ações e combates
até um Nexus chegar a 0, e conferir o desfecho sem que nenhuma fase automática
tenha sido observada.

- [X] T059 [US8] Criar `server/apps/game/tests/test_full_match.py` com uma partida montada por `fake_setup.py`, mulligan dos dois, e rodadas alternando ações, pilha e combate até um Nexus chegar a 0, conferindo o desfecho
- [X] T060 [US8] Acrescentar a `server/apps/game/tests/test_full_match.py` o cenário 2 da US8: coletar a fase observada depois de cada `submit_action` e afirmar que nenhuma foi `UPKEEP`, `STACK_RESOLUTION` ou `ROUND_END`
- [X] T061 [US8] Acrescentar a `server/apps/game/tests/test_full_match.py` o cenário 3 da US8: afirmar que nenhum módulo do caminho importou `redis`, `channels` nem `django.db`

**Checkpoint**: o motor está fechado.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: os textos que deixaram de ser previsão, e as portas de qualidade.

- [X] T062 Reescrever o docstring do pacote em `server/apps/game/engine/__init__.py` — o combate caiu no lugar que ele reservava — e conferir o `__all__` final contra [contracts/combat_resolution.md §7](./contracts/combat_resolution.md), com atenção aos sete nomes que **não** entram
- [X] T063 [P] Reescrever os três docstrings de `server/apps/game/engine/player_action.py` que previam esta feature: o do módulo ("declarar ataque entra igual"), o de `ActionKind` ("a ação que falta da §5") e o de `CastSpellAction` ("é outra ação — não esta com uma fase a mais")
- [X] T064 [P] Corrigir em `server/apps/game/engine/unit_vitals.py` a frase de `unit_has_damage_immunity` que diz que o combate a consulta "ao decidir bloqueio": quem a consulta é `deal_damage_to_unit`, e o combate herda a imunidade sem uma linha nova
- [X] T065 [P] Conferir que os cinco textos listados no [plan.md](./plan.md) como "não devem mudar" continuam idênticos — `bury_dead_units`, `check_victory`, o docstring de `spell_effect.py`, o de `spell_stack.py` e o de `BankUnit`
- [X] T066 Verificar a exaustividade do despacho: remover temporariamente um `case` de `_apply_action` em `server/apps/game/engine/round_cycle.py`, conferir que o `mypy` reprova por `assert_never`, e restaurar
- [X] T067 Rodar `cd server && black .` e conferir que nenhum arquivo desta feature ficou fora do formato
- [X] T068 Rodar `cd server && mypy` e confirmar verde sem nenhuma relaxação nova em `server/mypy.ini`
- [X] T069 Rodar `cd server && pytest` completo e confirmar a suíte inteira verde
- [X] T070 Conferir a checklist de tamanho: nenhum arquivo acima de 500 linhas — com atenção a `server/apps/game/engine/player_action.py`, que o plano prevê em ~470 —, nenhuma função acima de 20 linhas, no máximo 2 níveis de indentação
- [X] T071 Percorrer o [quickstart.md](./quickstart.md) inteiro no shell, incluindo o roteiro 5 do empate e o roteiro 7 da partida completa, conferindo que cada valor lido bate com o documentado
- [X] T072 Confirmar que nenhum arquivo de teste das features 001 a 006 mudou (research [D20](./research.md)); se algum inventário precisou mudar, registrar qual e por quê no [plan.md](./plan.md), como a feature 006 fez com os dois que encontrou

---

## Dependencies & Execution Order

### Phase Dependencies

- **Fase 1 (Setup)**: sem dependência.
- **Fase 2 (Foundational)**: depende da Fase 1. **Bloqueia todas as histórias** —
  todas as cinco regras leem `Match.combat`, e as quatro ações da janela leem
  `keeps_priority`.
- **Fase 3 (US1)**: depende da Fase 2.
- **Fase 4 (US2)**: depende da Fase 3 — o pareamento precisa de atacantes.
- **Fase 5 (US4)**: depende da Fase 4 — o dano lê o pareamento.
- **Fase 6 (US5)**: depende da Fase 5 — a limpeza chama o dano.
- **Fase 7 (US3)**: depende da Fase 3. **Pode correr em paralelo com as Fases 4,
  5 e 6** — arquivos diferentes, e o feitiço imediato não é pré-requisito de
  nada. T050 e T051 precisam da Fase 6.
- **Fase 8 (US6)**: depende da Fase 6.
- **Fase 9 (US7)**: depende só da Fase 2. Fica no fim por arrumação.
- **Fase 10 (US8)**: depende de todas as anteriores.
- **Fase 11 (Polish)**: depende de tudo.

### O único caminho crítico

```
Fase 2 ──> Fase 3 (US1) ──> Fase 4 (US2) ──> Fase 5 (US4) ──> Fase 6 (US5) ──> Fase 8 (US6)
              │                                                   │
              └──> Fase 7 (US3) ────────────────────────────────> ┘
                                                    (T050, T051)
```

A Fase 9 sai desse caminho por completo e pode ser feita a qualquer momento
depois da Fase 2.

### Within Each User Story

- Implementação antes dos testes, como nas features anteriores deste projeto: os
  contratos já estão escritos em `contracts/`, e o teste afirma o contrato, não
  o descobre.
- As recusas antes da regra que as levanta (T013 antes de T014, T020 antes de
  T021).
- A regra antes do braço que a chama (T014 antes de T015): o módulo sozinho
  compila, e o braço sem a regra não.
- A regra testável sozinha antes da ação que a dispara (Fase 5 antes da Fase 6).
- Consultas (`unit_vitals`) antes das mutações (`combat_damage`).

### Parallel Opportunities

- **T002 e T003** — duas leituras, nenhuma edição.
- **T005 e T004**? Não: T005 testa o que T004 cria. Mas **T005 e T009** são
  arquivos diferentes.
- **T009 e T011** — a visão e o tabuleiro de teste, sem relação.
- **T016 e T017**, **T023 e T024**, **T033, T034 e T035**, **T039 e T040**,
  **T047 e T048** — blocos de teste no mesmo arquivo, paralelos se escritos como
  funções independentes.
- **T028 e T030** — `unit_effective_attack` e `change_nexus_simultaneously`,
  duas funções sem relação no mesmo arquivo de teste.
- **Fase 7 e Fases 4–6** correm em paralelo por completo: `cast_spell.py`,
  `spell_cast_guards.py` e `cast_combat_spell.py` de um lado,
  `blocker_pairing.py`, `combat_damage.py` e `combat_cleanup.py` do outro. É a
  maior oportunidade da feature, e as duas frentes só se encontram em
  `player_action.py`, `round_cycle.py` e `engine/__init__.py`.
- **T055, T056 e T057** — três cenários de round-trip independentes.
- **T063, T064 e T065** — três arquivos diferentes no polimento.

---

## Parallel Example: depois da Fase 3

```bash
# Duas frentes, sem conflito de arquivo:

# Frente A -- quem bloqueia e quem apanha (Fases 4, 5, 6)
Task: "T020 Criar engine/blocker_pairing.py com as cinco recusas"
Task: "T027 Acrescentar unit_effective_attack a engine/unit_vitals.py"
Task: "T029 Acrescentar change_nexus_simultaneously a engine/victory.py"

# Frente B -- quem conjura (Fase 7)
Task: "T043 Criar engine/spell_cast_guards.py e reescrever cast_spell.py sobre ela"
Task: "T045 Criar engine/cast_combat_spell.py"
```

As duas frentes se encontram em `player_action.py`, `round_cycle.py` e
`engine/__init__.py` (T022, T038, T046) e na Fase 8, que consome as duas.

---

## Implementation Strategy

### MVP

A Fase 3 (US1) é a primeira coisa que um jogador consegue fazer, e é onde o 🎯
está. Mas ela sozinha entrega **uma partida que entra em Combate e trava lá** —
é MVP de formato, não de jogo.

### Parada útil

A primeira parada em que a feature vale alguma coisa é o **fim da Fase 6**:
declarar, bloquear, encerrar, o dano resolver, os mortos irem ao cemitério e a
partida voltar para a Fase de Ação. Antes disso o Combate é um beco sem saída.

Uma segunda parada defensável é o **fim da Fase 7**, que fecha a §7 inteira: com
o feitiço imediato, o defensor tem as três coisas que a §7.2 lhe dá, e não sobra
nada da nota por implementar.

### Entrega incremental

1. Fases 1–2 → o estado existe e atravessa o Redis; a suíte antiga intacta
2. Fase 3 → a partida alcança `COMBAT` pela primeira vez
3. Fase 4 → o defensor bloqueia, e a prioridade não sai dele
4. Fase 5 → o dano está correto, testado sobre estados montados
5. **Fase 6 → o combate roda inteiro por ações de jogador. Parada útil.**
6. **Fase 7 → a §7 fechada.**
7. Fases 8–9 → a rodada e o Redis conferidos
8. Fase 10 → a partida inteira, do setup à vitória
9. Fase 11 → os textos e as portas de qualidade

### Parallel Team Strategy

Com dois desenvolvedores, depois da Fase 3:

- **A** faz as Fases 4, 5 e 6 — bloqueio, dano e limpeza
- **B** faz a Fase 7 — a extração das guardas e o feitiço imediato
- Os dois se encontram nos três arquivos compartilhados e na Fase 8

Com três, o terceiro pega a Fase 9 desde cedo: o round-trip do `CombatState` já
é escrevível ao fim da Fase 2.

---

## Notes

- `[P]` = arquivo diferente, sem dependência pendente
- `[Story]` mapeia a tarefa para a história, para rastreabilidade
- Toda tarefa cita o arquivo exato; nenhuma cita "vários arquivos"
- Commit por tarefa ou por grupo lógico; a suíte fica verde em todo checkpoint
- **T008, T012, T015, T022, T038, T043 e T046 são atômicas** — dividi-las derruba
  a checagem inteira, não um arquivo
- **T044 é uma porta, não uma formalidade**: se `test_cast_spell.py` precisar de
  uma linha nova, T043 mudou comportamento e o plano precisa ser relido
- **A Fase 5 vem antes da Fase 6** — o dano testado sobre estado montado antes de
  existir a ação que o dispara; é o corte que a feature 006 fez com
  `resolve_stack`, e ele existe para que um erro no cálculo apareça sem a
  cascata no meio
- O plano previa 7 arquivos de teste novos; são **8**. `test_combat_state.py`
  entrou na Fase 2 porque `CombatState` e `ongoing_combat()` são funções novas e
  o princípio V exige teste para cada uma — e porque pôr esses testes em
  `test_match_state.py` quebraria a promessa de não tocar arquivo de teste
  existente
- Os testes de `change_nexus_simultaneously` e de `unit_effective_attack` moram
  em `test_combat_damage.py`, e não em `test_victory.py` nem em
  `test_unit_damage.py`, pela mesma razão: as duas funções existem para o
  combate, e os arquivos antigos ficam intocados
- Nenhum arquivo de teste das features 001 a 006 é alterado. Se um deles precisar
  mudar, é sinal de que o desenho divergiu do plano — pare e releia research
  [D20](./research.md)
