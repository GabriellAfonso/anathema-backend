---

description: "Task list for 008-instant-spells"
---

# Tasks: Feitiço imediato

**Input**: Design documents from `specs/008-instant-spells/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/cast_spell.md](./contracts/cast_spell.md),
[contracts/removed_surface.md](./contracts/removed_surface.md),
[quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. O princípio V da constituição exige teste
para toda função nova e teste de regressão que falhe antes da correção — e esta
feature é a correção de uma regra.

**Organization**: agrupadas por história de usuário, na ordem que as dependências
permitem. Onde a ordem diverge da spec, a razão está escrita abaixo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a que história pertence (US1 a US5)
- Todo caminho de arquivo é relativo à raiz do repositório

## Estratégia de corte

Esta feature é de remoção, e remoção quebra em cadeia: apagar um nome derruba
todo import dele, e o mypy strict reprova a suíte inteira, não um arquivo. A
suíte precisa ficar verde em todo checkpoint de fase, e para isso três grupos de
edição precisam ir **juntos, num commit só**.

- **T008 + T009 — a ação única.** Tirar `CastCombatSpellAction` da união exige
  tirar o `case` de `_apply_action` (o `assert_never` reprova o braço órfão), o
  export de `engine/__init__.py`, e todo teste que o importa. Mudar
  `CastSpellAction` para resolver na hora quebra todo teste que joga feitiço por
  `submit_action` esperando pilha — e `test_stack_resolution.py` inteiro faz
  isso. A produção é T008, os testes que ela quebra são T009; entre as duas a
  suíte está vermelha.
- **T013 + T014 — a cascata e o ataque sem pilha.** Independentes entre si
  (arquivos diferentes), mas cada uma apaga código e o teste que o exercita na
  mesma tarefa.
- **T017 + T018 — o estado sem pilha.** Tirar `Match.stack` e
  `StackEntryDocument` derruba `fake_match_state.py`, que é importado por metade
  da suíte. A produção é T017, os testes são T018.

### Por que US1 e US2 são uma fase só

A spec separa "feitiço na Fase de Ação" (US1) de "feitiço do defensor" (US2),
porque o jogador vive as duas em momentos diferentes. No código elas deixam de
ser duas coisas: são **uma** ação, e tirar `CastCombatSpellAction` é a mesma
edição que dar `{ACTION, COMBAT}` a `CastSpellAction`. Fazer US1 sem US2 deixaria
o defensor sem ação de feitiço nenhuma entre as duas fases. As tarefas levam o
rótulo da história que provam.

| Fase | História | Depende de | Por quê |
|---|---|---|---|
| 1 | — | — | Conferir números e o ponto de partida. |
| 2 | — | — | Vazia: a primeira edição já é a regra. |
| 3 | US1 + US2 | Fase 1 | A ação única. Depois dela nada empilha, e o resto da pilha vira código morto. |
| 4 | US3 | Fase 3 | A saída da §5 e a guarda de ataque só podem perder o ramo da pilha depois que nada mais a enche. |
| 5 | US4 | Fase 4 | O estado só perde `stack` e `STACK_RESOLUTION` depois que nenhuma regra os lê. |
| 6 | US5 | Fase 5 | A partida completa com feitiço afirma o estado final, sem pilha. |
| 7 | — | tudo | Comentários que só afirmam, e as portas. |

---

## Phase 1: Setup

**Purpose**: conferir o ponto de partida e os números que os testes vão medir.

- [X] T001 Rodar `cd server && pytest && mypy && black --check .` e confirmar as três portas verdes antes de qualquer edição
- [X] T002 [P] Conferir em `server/apps/game/cards/mvp_catalog.py` os números que os testes e o contrato usam — SOMEONE'S SHIELD custa 2, MAGIC BARRIER 3, SACRIFICIAL FIRE 8 (e 8 de Nexus), LIFE POTION 4, SUMMONED AX 5 (3 de dano), e MORTEM com 2 de vida — e corrigir [contracts/cast_spell.md](./contracts/cast_spell.md) e [quickstart.md](./quickstart.md) se algum divergir
- [X] T003 [P] Confirmar a premissa de [research.md D12](./research.md#d12-uma-partida-completa-com-feitiço-de-verdade) lendo `server/apps/game/cards/starter_deck.py` e a ordem de `card_id` em `server/apps/game/cards/mvp_catalog.py`: o deck de andaime não contém nenhum `card_id` de 1001 a 1005

---

## Phase 2: Foundational (Blocking Prerequisites)

Nenhuma tarefa. Não há estado nem porta nova a preparar: a primeira edição de
produção (T008) já é a regra corrigida.

---

## Phase 3: User Story 1 + User Story 2 - A ação única: resolve na hora e fica com a vez (Priority: P1) 🎯 MVP

**Goal**: jogar feitiço é uma ação só, legal na Fase de Ação e na janela do
defensor; o efeito acontece na jogada, a carta vai ao cemitério depois dele, os
passes zeram, e a vez fica com quem jogou.

**Independent Test**: na Fase de Ação, jogar SUMMONED AX em MORTEM e conferir,
sem nenhum passe, MORTEM e depois AX nos cemitérios, energia menos 5, prioridade
ainda com quem jogou, passes em 0; jogar um segundo feitiço e ver aceito; jogar
uma unidade e ver a vez passar. No Combate, o defensor faz o mesmo com a mesma
ação, e o atacante é recusado por prioridade.

### Tests for User Stories 1 and 2 ⚠️

> Escrever primeiro. T004 a T007 falham contra o código atual, e é isso que os
> torna teste de regressão.

- [X] T004 [P] [US1] Criar `server/apps/game/tests/test_cast_spell_refusals.py` com as recusas de `server/apps/game/tests/test_cast_spell.py` (seção "As recusas", de `test_an_untargeted_spell_refuses_a_target` até `test_a_refusal_never_advances_the_match_counters`) e de `server/apps/game/tests/test_cast_combat_spell.py` (seção "As recusas"), sem duplicata, todas com `CastSpellAction`. Os cenários de alvo e energia rodam parametrizados nas duas fases (Fase de Ação via `fake_spell_board`, Combate via `fake_combat_board` com o ataque já declarado). Incluir `test_the_attacker_cannot_cast_in_the_window` esperando `NotYourPriorityError`. Não trazer `test_a_refusal_leaves_the_stack_alone`. Afirmar partida intocada com o snapshot de `server/apps/game/tests/match_snapshot.py`, como os originais. Abaixo de 500 linhas.
- [X] T005 [US1] Reescrever `server/apps/game/tests/test_cast_spell.py` (depende de T004, que tira as recusas dele) só com o lançamento aceito, conforme [contracts/cast_spell.md](./contracts/cast_spell.md): `test_the_effect_happens_on_the_cast`, `test_the_spell_card_goes_to_the_graveyard_after_the_units_it_killed`, `test_the_energy_is_spent`, `test_energy_exactly_equal_to_the_cost_is_accepted`, `test_the_priority_stays_with_the_caster`, `test_a_second_spell_in_the_same_turn_is_accepted`, `test_a_unit_after_a_spell_gives_the_turn_back`, `test_the_pass_count_is_reset`, `test_a_pass_after_a_spell_does_not_close_the_round` (B passa, A joga feitiço e passa: `consecutive_passes == 1`, vez de B, fase `ACTION`), `test_an_untargeted_spell_resolves_on_the_cast` (LIFE POTION), `test_a_permanent_modifier_is_there_on_the_cast` (SOMEONE'S SHIELD), `test_an_enemy_target_is_accepted`, `test_the_opponent_side_is_otherwise_untouched`, `test_passing_still_works_with_an_empty_hand`, e `test_both_phases_give_the_same_state` — herdeiro de `test_both_paths_give_the_same_state` de `server/apps/game/tests/test_cast_combat_spell.py`, com `_apply_in_action_phase` e `_apply_in_combat` usando a mesma `CastSpellAction`, `_comparable` ignorando só `phase` e `combat`, e **sem** SACRIFICIAL FIRE no laço ([research.md D9a](./research.md)). Nenhum teste afirma SACRIFICIAL FIRE nem a duração da MAGIC BARRIER. Abaixo de 500 linhas.
- [X] T006 [P] [US2] Criar `server/apps/game/tests/test_spell_in_combat.py` com as seções "Resolve na hora" (menos `test_the_stack_stays_empty`), "O que o feitiço muda no dano" e "A partida que acaba dentro da janela" de `server/apps/game/tests/test_cast_combat_spell.py`, e o auxiliar `_block`, trocando `CastCombatSpellAction` por `CastSpellAction`. Manter `test_the_priority_stays_with_the_defender` e `test_two_spells_in_the_same_window`. Os dois testes da partida que acaba dentro da janela e `test_an_immune_blocker_takes_nothing_and_the_attacker_takes_its_share` vêm sem mudança de afirmação, com docstring dizendo que a feature da §14 os reescreve ([research.md D9](./research.md)).
- [X] T007 [P] [US1] Em `server/apps/game/tests/test_blocker_pairing.py`, tirar `CastSpellAction` de `test_every_action_phase_arm_gives_the_turn_back` (que passa a afirmar só `PlayUnitAction`, `PassAction`, `DeclareAttackAction`, com docstring dizendo que são as três que devolvem a vez) e criar `test_the_spell_keeps_the_turn_in_both_phases` afirmando `CastSpellAction.keeps_priority` e `CastSpellAction.allowed_phases == frozenset({MatchPhase.ACTION, MatchPhase.COMBAT})`

### Implementation for User Stories 1 and 2

> T008 e T009 são um commit só. Ver "Estratégia de corte".

- [X] T008 [US1] O corte de produção da ação única, centrado em `server/apps/game/engine/cast_spell.py` e `server/apps/game/engine/player_action.py` ([research.md D1–D3, D8](./research.md)):
  - `server/apps/game/engine/player_action.py`: `CastSpellAction.allowed_phases = frozenset({MatchPhase.ACTION, MatchPhase.COMBAT})`, `keeps_priority = True`; docstring da classe diz que é a ação B da §5 e o feitiço da §7.2, resolve na hora e não passa a vez (sem citar `StackEntry` nem "outra ação"); tirar `CastCombatSpellAction` do import e da união `PlayerAction`; o docstring do módulo passa a dizer que a exceção à alternância são o feitiço e a janela do defensor
  - `server/apps/game/engine/combat_action.py`: apagar `CastCombatSpellAction`; docstring do módulo fala em três ações da janela e aponta `CastSpellAction` como o feitiço dela
  - `server/apps/game/engine/action_kind.py`: apagar `CAST_COMBAT_SPELL`; docstring conta sete espécies
  - `server/apps/game/engine/cast_spell.py`: reescrever com o corpo de `server/apps/game/engine/cast_combat_spell.py` na ordem de [contracts/cast_spell.md](./contracts/cast_spell.md#pós-condições-aceita) — guardas, energia, mão, `apply_spell_effect`, cemitério, `consecutive_passes = 0`; docstring do módulo herda a razão da ordem efeito → cemitério e diz por que a zeragem vale nas duas fases (D2)
  - apagar `server/apps/game/engine/cast_combat_spell.py`
  - `server/apps/game/engine/spell_cast_guards.py`: `validated_spell_cast(match, actor, action: CastSpellAction, *, catalog)`; docstrings do módulo, de `ValidatedSpellCast`, de `validated_spell_cast` e de `SpellTargetNotOnBattlefieldError` sem "empilha", "caminho da pilha", "fizzle" nem `StackEntry` — alvo fora de campo é sempre recusa
  - `server/apps/game/engine/round_cycle.py`: tirar o import e o `case CastCombatSpellAction()` de `_apply_action`; docstring de `_pass_priority` troca "a única exceção à alternância" pelas duas (feitiço e janela)
  - `server/apps/game/engine/__init__.py`: tirar `CastCombatSpellAction` do import e do `__all__`; docstring do pacote troca "a pilha de feitiços da §6" por "o feitiço imediato da §5B"
- [X] T009 [US1] Os testes que T008 quebra, em `server/apps/game/tests/`:
  - apagar `server/apps/game/tests/test_cast_combat_spell.py` (conteúdo já redistribuído em T004, T005, T006)
  - apagar `server/apps/game/tests/test_stack_resolution.py` (todo cenário joga feitiço esperando que ele empilhe)
  - `server/apps/game/tests/test_blocker_pairing.py`: tirar `CastSpellAction` de `test_the_defender_cannot_use_the_action_phase_actions` — a lista de ações proibidas no combate (achado na implementação; faltava no inventário de research.md D11)
  - `server/apps/game/tests/test_combat_cleanup.py`: `test_the_stack_path_works_again_after_the_combat` vira `test_a_unit_after_the_combat_gives_the_turn_back` — depois do combate, B joga uma unidade e a vez passa a A; docstrings das linhas ~302 e ~357 sem `STACK_RESOLUTION` nem `test_cast_combat_spell.py`
  - `server/apps/game/tests/test_spell_state_round_trip.py`: `played_out_match` joga os feitiços respeitando a vez (A joga SOMEONE'S SHIELD e SACRIFICIAL FIRE, passa; B joga MAGIC BARRIER — o FIRE fica porque é o único produtor de `AttackModifier`, com comentário apontando a §14); apagar `test_a_full_stack_survives_the_round_trip`; renomear `test_a_stacked_match_is_stable_across_the_round_trip` para `test_a_match_after_spells_is_stable_across_the_round_trip`; `test_the_three_modifier_kinds_survive_the_round_trip` sem `pass_until_priority_returns` (apagar o auxiliar se ficar sem uso); docstring do módulo sem pilha
- [X] T010 [US1] Checkpoint em `server/`: `cd server && pytest && mypy` verdes; T004 a T007 passando

**Checkpoint**: jogar feitiço resolve na hora e fica com a vez nas duas fases. A
pilha ainda existe no código, mas nada a enche.

---

## Phase 4: User Story 3 - A rodada fecha com dois passes, e o ataque não espera nada (Priority: P1)

**Goal**: a saída da §5 tem um ramo só, a cascata é Fim de Rodada e Upkeep, e
declarar ataque tem cinco guardas.

**Independent Test**: A joga um feitiço e passa, B passa, a rodada fecha com o
Upkeep executado; o dono do token joga dois feitiços e declara ataque na mesma
vez.

### Tests for User Story 3

- [X] T011 [P] [US3] Em `server/apps/game/tests/test_round_cycle.py`, criar `test_two_passes_after_a_spell_close_the_round` (A joga LIFE POTION e passa, B passa: rodada 2, fase `ACTION`, Upkeep executado)
- [X] T012 [P] [US3] Em `server/apps/game/tests/test_declare_attack.py`, criar `test_spells_then_an_attack_in_the_same_turn` (dono do token joga dois feitiços e declara ataque; as três aceitas; a vez passa ao defensor só na terceira)

### Implementation for User Story 3

- [X] T013 [P] [US3] A cascata sem pilha em `server/apps/game/engine/round_cycle.py` ([research.md D5, D6](./research.md)):
  - `server/apps/game/engine/round_cycle.py`: `_exit_action_phase` com um ramo (`consecutive_passes >= CONSECUTIVE_PASSES_TO_EXIT` → `ROUND_END`); `_AUTOMATIC_PHASES = frozenset({MatchPhase.ROUND_END, MatchPhase.UPKEEP})`; `_run_automatic_phase` com dois ramos; tirar `catalog` de `_settle` e de `_run_automatic_phase` e da chamada em `submit_action`; tirar o import de `resolve_stack`; docstrings do módulo, de `_exit_action_phase` e de `_settle` sem pilha ("termina em no máximo uma volta completa: `ROUND_END` leva a `UPKEEP`, que leva a `ACTION`")
  - apagar `server/apps/game/engine/stack_resolution.py`
  - `server/apps/game/tests/test_round_cycle.py`: apagar a seção "A costura da pilha" (`test_the_stack_stays_empty_across_ten_rounds`, `test_the_stack_branch_of_the_exit_is_wired`), o parágrafo do docstring do módulo que a explica, e o import de `StackEntry`
- [X] T014 [P] [US3] Declarar ataque sem pilha em `server/apps/game/engine/declare_attack.py` ([research.md D7](./research.md)):
  - `server/apps/game/engine/declare_attack.py`: apagar `StackIsNotEmptyError`, `_ensure_stack_is_empty` e a chamada; docstring do módulo com cinco guardas renumeradas
  - `server/apps/game/engine/__init__.py`: tirar `StackIsNotEmptyError` do import e do `__all__`
  - `server/apps/game/tests/test_declare_attack.py`: apagar `test_a_full_stack_is_refused_naming_the_size`, os imports de `StackIsNotEmptyError` e `StackEntry`, e as menções a Resolução de Pilha nos docstrings (linhas ~9 e ~229)
- [X] T015 [US3] Checkpoint em `server/`: `cd server && pytest && mypy` verdes; T011 e T012 passando

**Checkpoint**: nenhuma regra lê a pilha. Ela ainda existe no estado.

---

## Phase 5: User Story 4 - Nenhum resto de pilha na partida (Priority: P2)

**Goal**: estado, forma gravada, visão e fases sem pilha.

**Independent Test**: gravar e reler uma partida, montar a visão, listar as
fases; nenhum tem pilha.

### Tests for User Story 4

- [X] T016 [P] [US4] Criar `test_the_document_has_no_stack_key` em `server/apps/game/tests/test_match_serialization.py` e `test_the_view_has_no_stack_key` em `server/apps/game/tests/test_player_view.py` (os dois falham até T017)

### Implementation for User Story 4

> T017 e T018 são um commit só.

- [X] T017 [US4] O estado sem pilha em `server/apps/game/match/` ([research.md D4](./research.md)):
  - apagar `server/apps/game/match/spell_stack.py`
  - `server/apps/game/match/match_state.py`: apagar `MatchPhase.STACK_RESOLUTION`, o campo `stack` com o comentário dele e o import de `StackEntry`; docstring de `bank_unit` troca "autoriza o fizzle" pelo bloqueador órfão da §7.3
  - `server/apps/game/match/documents.py`: apagar `StackEntryDocument` e a chave `stack` de `MatchDocument`
  - `server/apps/game/match/serialization.py`: apagar `to_stack_entry_document`, `stack_entry_from_document`, as duas linhas que os usam e os imports; docstring do módulo sem "ordem da pilha"
  - `server/apps/game/match/player_view.py`: apagar a chave `stack` e os imports; o comentário de `combat` troca "como a pilha" por "como o cemitério"
  - `server/apps/game/match/__init__.py`: tirar `StackEntry` e `StackEntryDocument` do import e do `__all__`
- [X] T018 [US4] Os testes que T017 quebra, em `server/apps/game/tests/`:
  - apagar `server/apps/game/tests/test_spell_stack.py`
  - `server/apps/game/tests/fake_match_state.py`: apagar `_fill_stack`, a chamada, o import e "e pilha" do docstring
  - `server/apps/game/tests/test_match_serialization.py`: apagar `test_stack_order_is_preserved` e os dois testes de alvo na pilha (~134 e ~142); docstring do módulo sem pilha
  - `server/apps/game/tests/test_match_state.py`: tirar `"stack_resolution"` de `test_the_phase_set_is_closed`; apagar `test_new_match_has_an_empty_stack`
  - `server/apps/game/tests/test_match_store.py`: `test_card_identity_survives_the_round_trip` pergunta `reloaded.bank_unit(...)` pelo identificador de uma unidade do banco de `fake_match_in_progress`, e o docstring fala do alvo de um feitiço ou de um bloqueio; docstring da linha ~64 sem pilha
  - `server/apps/game/tests/test_card_instance_identity.py`: docstrings de quatro zonas; `_all_identifiers` sem a linha da pilha
  - `server/apps/game/tests/test_match_setup.py`: apagar `assert match.stack == []`
  - `server/apps/game/tests/test_play_unit.py`: apagar `test_playing_a_unit_does_not_use_the_stack`
  - `server/apps/game/tests/test_player_action.py`: tirar `MatchPhase.STACK_RESOLUTION` do parametrize
  - `server/apps/game/tests/test_player_view.py`: apagar `test_the_stack_appears_in_order`
  - `server/apps/game/tests/test_full_match.py`: tirar `and not match.stack` de `_can_attack`; tirar `STACK_RESOLUTION` do docstring do módulo
- [X] T019 [US4] Checkpoint em `server/`: `cd server && pytest && mypy` verdes; T016 passando

**Checkpoint**: nenhum nome de [contracts/removed_surface.md](./contracts/removed_surface.md) resolve em `apps.game`.

---

## Phase 6: User Story 5 - Uma partida inteira com feitiço imediato (Priority: P3)

**Goal**: uma partida roda do setup à vitória com feitiço aceito nas duas fases.

**Independent Test**: `test_full_match.py` verde, com o teste novo afirmando
`CastSpellAction` aceito em `ACTION` e em `COMBAT`.

- [X] T020 [US5] Em `server/apps/game/tests/test_full_match.py` ([research.md D12](./research.md#d12-uma-partida-completa-com-feitiço-de-verdade)):
  - montar um deck válido com as cartas de feitiço menos o SACRIFICIAL FIRE (3 cópias cada) e unidades do catálogo até 40, e passá-lo ao setup — por parâmetro novo em `server/apps/game/tests/fake_setup.py::fake_match_in_action_phase` se ficar mais simples que montar a partida no teste
  - `next_action`: na Fase de Ação, antes de unidade/ataque/passe, o feitiço mais barato que caiba na energia e tenha alvo válido (sem alvo, ou unidade do lado que o efeito pede); no Combate, o defensor joga um feitiço se puder, senão encerra a janela
  - `play_until_over` registra `(fase antes da ação, action_kind)`; os testes existentes continuam lendo as fases observadas
  - criar `test_spells_are_cast_in_both_phases`
  - docstring do módulo: o jogador automático joga feitiço, e o laço termina porque todo feitiço do MVP custa pelo menos 2 de energia
- [X] T021 [US5] Checkpoint: `cd server && pytest apps/game/tests/test_full_match.py` verde, e todos os testes do arquivo — inclusive `test_no_automatic_phase_is_ever_observed` e `test_the_match_never_stalls_in_combat` — sem mudança de afirmação. **Desvio na implementação**: `test_the_match_never_stalls_in_combat` precisou mudar — com o defensor jogando feitiço, Combate aparece em jogadas seguidas legitimamente; a afirmação passou a ser que toda jogada que mantém a janela aberta é um feitiço

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T022 [P] Reescrever os docstrings do motor que ainda afirmam pilha, conforme a tabela de [research.md D10](./research.md#d10-os-comentários-que-afirmam-a-pilha): `server/apps/game/engine/spell_effect.py` (módulo, `SpellEffectNeedsTargetError`, `apply_spell_effect`), `server/apps/game/engine/play_unit.py`, `server/apps/game/engine/round_end.py`, `server/apps/game/engine/card_draw.py`, `server/apps/game/engine/unit_damage.py`, `server/apps/game/engine/combat_cleanup.py`, `server/apps/game/engine/deck_reset.py`
- [X] T023 [P] Reescrever os docstrings do estado: `server/apps/game/match/cards_in_play.py`, `server/apps/game/match/combat_state.py`
- [X] T024 [P] Reescrever os docstrings de teste: `server/apps/game/tests/test_combat_damage.py`, `server/apps/game/tests/test_spell_effect.py` (linhas ~3, ~11, ~184, ~468, ~488), `server/apps/game/tests/test_card_draw.py`, `server/apps/game/tests/test_round_end.py`, `server/apps/game/tests/test_setup_randomness.py`, `server/apps/game/tests/fake_combat_board.py`, `server/apps/game/tests/fake_spell_board.py`; "pilha de compra" vira "monte de compra" em `server/apps/game/tests/test_player_view.py` e `server/apps/game/tests/test_match_serialization.py`
- [X] T025 [P] Em `server/apps/game/tests/test_spell_effects.py`, apagar `test_target_properties_read_the_same_twice` — as duas leituras eram lançamento e resolução, e só existe uma
- [X] T026 Rodar `rg -i "pilha|stack|fizzl|empilh|CastCombatSpell|cast_combat_spell|STACK_RESOLUTION" server/apps/game` e zerar o que sobrar, exceto as linhas dos dois testes de ausência da chave `stack` (depende de T022–T025)
- [X] T027 Rodar as portas: `cd server && pytest && mypy && black --check .`; se `black` reclamar, `black` nos arquivos alterados e rodar de novo
- [X] T028 Conferir que nenhum arquivo tocado passou de 500 linhas (`wc -l` em `server/apps/game/engine/*.py server/apps/game/match/*.py server/apps/game/tests/*.py`) e que nenhuma função nova passou de 20
- [X] T029 Seguir os cenários 1 a 8 de [quickstart.md](./quickstart.md#cenários-para-conferir-à-mão) e corrigir o quickstart onde a execução divergir do texto

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sem dependência
- **Foundational (Fase 2)**: vazia
- **US1 + US2 (Fase 3)**: depende da Fase 1
- **US3 (Fase 4)**: depende da Fase 3 — sem ela, `_exit_action_phase` ainda tem feitiço pendente para mandar à resolução
- **US4 (Fase 5)**: depende da Fase 4 — sem ela, `round_cycle.py` e `declare_attack.py` ainda leem `match.stack`
- **US5 (Fase 6)**: depende da Fase 5 — o `_can_attack` do teste só perde `match.stack` quando o campo some; tecnicamente a partida com feitiço já roda depois da Fase 3
- **Polish (Fase 7)**: depende de tudo

### O caminho crítico

T004 → T005 → T008 + T009 → T013 + T014 → T017 + T018 → T020 → T026 → T027

Cada `+` é um commit só.

### Within Each User Story

- Testes antes da implementação, e falhando antes dela (exceto T011 e T012, que
  afirmam comportamento já entregue pela Fase 3 e servem de guarda contra
  regressão na remoção)
- Produção e os testes que ela quebra no mesmo commit
- Checkpoint verde antes da fase seguinte

### Parallel Opportunities

- T002, T003
- T004, T006, T007 (arquivos novos ou diferentes); T005 espera T004
- T011, T012
- T013, T014 (arquivos diferentes; só T014 toca `engine/__init__.py`, e T008 já terminou)
- T022, T023, T024, T025

---

## Parallel Example: Fase 3

```text
Em paralelo:
  T004 test_cast_spell_refusals.py (lê as recusas de test_cast_spell.py e test_cast_combat_spell.py)
  T006 test_spell_in_combat.py
  T007 test_blocker_pairing.py

Depois de T004:
  T005 test_cast_spell.py

Depois de T004–T007, um commit:
  T008 produção
  T009 testes quebrados
```

---

## Implementation Strategy

### MVP

Fases 1 e 3. Depois de T010 o jogo joga certo: feitiço resolve na hora e fica
com a vez nas duas fases. O que falta é remoção de código morto (Fases 4 e 5) e
a prova de integração (Fase 6).

### Parada útil

Depois da Fase 4 (T015), nenhuma regra conhece a pilha. Se a feature precisar
parar aí, o que sobra é estado sempre vazio — mas **a feature 009 não deve
começar antes da Fase 5**, porque publicaria `stack` e `stack_resolution` para o
cliente.

### Entrega incremental

Um commit por checkpoint (T010, T015, T019, T021) e um de polish. Cada um deixa
`pytest` e `mypy` verdes.

---

## Notes

- A spec da feature 009 não é tocada aqui ([research.md D14](./research.md#d14-a-spec-da-feature-009)).
- `[P]` = arquivos diferentes, sem dependência pendente.
- Toda contagem de linha citada ("~302") é a de antes da feature, e se desloca
  conforme as tarefas anteriores editam o arquivo.

## Registro da implementação (2026-09-11)

- **A nota mudou no meio da implementação.** Uma segunda correção do Fluxo de
  Partida (§4, §7.1, §10, §14, §15) chegou depois de T005. Com o dono do
  produto, ficou decidido que a 008 segue só com a remoção da pilha; os testes
  novos não afirmam nada sobre SACRIFICIAL FIRE e MAGIC BARRIER que a §14 mudou,
  e os três testes da feature 007 que dependem dessas cartas vieram sem mudança
  de afirmação, com docstring apontando a feature da §14. Ver research.md D9a.
- **T005**: `test_the_spell_card_goes_to_the_graveyard_after_the_units_it_killed`
  virou `test_the_killed_unit_and_the_spell_card_land_in_their_graveyards`. A
  ordem entre unidade morta e carta do feitiço só seria observável no mesmo
  cemitério, e nenhuma carta do MVP mata unidade do próprio lançador.
- **T007**: `test_the_spell_keeps_the_turn_in_both_phases` foi para
  `test_cast_spell.py` em vez de `test_blocker_pairing.py`, que já passava de
  500 linhas antes desta feature (532).
- **T009**: faltava no inventário `test_the_defender_cannot_use_the_action_phase_actions`,
  que afirmava feitiço proibido no combate.
- **T016**: os dois testes de ausência foram escritos no mesmo passo de T017, e
  não rodados vermelhos antes.
- **T021**: `test_the_match_never_stalls_in_combat` mudou de afirmação (ver a
  tarefa).
- **Portas**: `pytest` com 632 passando e 29 erros, todos de
  `test_match_store.py` e `test_matchmaking_queue.py`, que precisam do Redis em
  `anathema_redis` — o Docker não estava rodando na máquina, e os mesmos 29 já
  falhavam antes da feature. `test_match_store.py` foi editado (T018) e passa no
  mypy, mas não rodou. `mypy` e `black --check` limpos.
- **Tamanho**: `test_blocker_pairing.py` (535) e `test_spell_effect.py` (558)
  continuam acima de 500 linhas, como já estavam antes da feature.
