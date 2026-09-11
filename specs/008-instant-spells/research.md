# Research: Feitiço imediato

**Feature**: `008-instant-spells` | **Date**: 2026-09-11

Nenhum item da Technical Context ficou em aberto. O que segue são as decisões
de desenho, cada uma com a alternativa descartada, e o inventário do que muda.

A regra vem de `Game/Fluxo de Partida.md`, corrigida em 2026-09-11 em duas
passadas: primeiro "não existe pilha, feitiço resolve na hora", depois "e não
passa a vez".

---

## D1. Uma ação de feitiço, com `keeps_priority = True`

**Decision**: `CastSpellAction` fica, em `player_action.py`, com
`allowed_phases = frozenset({MatchPhase.ACTION, MatchPhase.COMBAT})` e
`keeps_priority = True`. `CastCombatSpellAction` sai de `combat_action.py`, e
`ActionKind.CAST_COMBAT_SPELL` sai de `action_kind.py`. A união `PlayerAction`
passa de oito braços a sete.

**Rationale**: as duas ações de hoje só diferiam em duas coisas, e as duas
sumiram com a correção. Uma empilhava e a outra resolvia — agora as duas
resolvem. Uma devolvia a vez e a outra não — agora nenhuma devolve. Sobram os
mesmos campos (`actor_user_id`, `card_instance_id`,
`target_card_instance_id`), o mesmo efeito e a mesma prioridade. O docstring de
`CastCombatSpellAction` justificava a própria existência com "as duas ações
fazem coisas diferentes com eles"; isso deixou de ser verdade.

O atacante continua sem poder jogar feitiço durante o combate, e continua sem
guarda nova para isso: a prioridade está com o defensor, e
`ensure_action_allowed` recusa por prioridade antes de olhar a fase.

`ActionKind.CAST_SPELL` mantém o valor `"cast_spell"`. É o que a feature 009 vai
publicar.

**Alternatives considered**:

- *Manter as duas ações.* Rejeitada: dois tipos idênticos em campo, efeito e
  prioridade, e a feature 009 publicaria ao cliente dois tipos de mensagem para
  o mesmo gesto — com uma recusa de fase para quem mandar o "errado".
- *Uma ação com `keeps_priority` dependendo da fase.* Rejeitada: era a saída
  para a primeira versão da correção, em que o feitiço da Fase de Ação passava a
  vez. Com a segunda, a resposta é a mesma nas duas fases, e `ClassVar[bool]`
  continua bastando.

---

## D2. `cast_spell.py` com o corpo de `cast_combat_spell.py`

**Decision**: `cast_spell(match, actor, action, *, catalog)` faz, nesta ordem:

1. `validated_spell_cast` — as guardas (D3)
2. desconta a energia
3. tira a carta da mão
4. `apply_spell_effect` com o alvo que a guarda resolveu
5. põe a carta no cemitério de quem jogou
6. `match.consecutive_passes = 0`

`cast_combat_spell.py` é apagado. O docstring do módulo novo herda a razão da
ordem 4 → 5 que `cast_combat_spell` já escrevia: uma unidade morta pelo efeito
entra no cemitério antes da carta do feitiço.

**Rationale**: é literalmente o caminho que já existe e já está testado. O nome
`cast_spell.py` diz "a ação B da §5", e é o que ele continua sendo.

A zeragem vale nas duas fases. Na janela do defensor ela não tem efeito — a
declaração já zerou e a limpeza da §7.4 zera de novo —, e escrevê-la sem
condição evita um `if` de fase que seria o primeiro passo para os dois caminhos
divergirem.

**Alternatives considered**:

- *Manter o nome `cast_combat_spell.py`.* Rejeitada: o nome afirmaria que é do
  combate.
- *Zerar passes só na Fase de Ação.* Rejeitada: um `if` sem efeito observável, e
  exatamente o tipo de ramo que `spell_effect.py` recusa ter.

---

## D3. `validated_spell_cast` recebe a ação

**Decision**: a assinatura passa de
`validated_spell_cast(match, actor, card_instance_id, target_card_instance_id, *, catalog)`
para `validated_spell_cast(match, actor, action: CastSpellAction, *, catalog)`.
O módulo `spell_cast_guards.py` fica, com as cinco recusas.

**Rationale**: o docstring de hoje justifica os identificadores soltos por
serem "dois braços que a chamam, de tipos diferentes". Com um braço só, o motivo
acabou.

**Alternatives considered**:

- *Devolver as guardas para dentro de `cast_spell.py`*, como `play_unit.py` e
  `declare_attack.py` fazem. Rejeitada nesta feature: move 300 linhas sem mudar
  comportamento, numa feature que já mexe em muita coisa. As guardas e as cinco
  recusas formam um módulo coeso por si. Fica anotado como opção futura, sem
  urgência.
- *Manter os identificadores soltos.* Rejeitada: sobraria uma justificativa
  falsa no docstring, ou nenhuma.

---

## D4. A pilha sai do estado, do documento e da visão

**Decision**: saem

- `match/spell_stack.py` inteiro, com `StackEntry`
- `Match.stack` e o import de `StackEntry` em `match_state.py`
- `StackEntryDocument` e a chave `stack` de `MatchDocument`, em `documents.py`
- `to_stack_entry_document`, `stack_entry_from_document` e as duas linhas que os
  usam, em `serialization.py`
- a chave `stack` de `PlayerView`, em `player_view.py`
- `StackEntry` e `StackEntryDocument` do `__all__` de `match/__init__.py`

**Rationale**: FR-015 a FR-017. Um campo que é sempre lista vazia não é
inofensivo: a feature 009 o publicaria ao cliente como parte do jogo.

**Alternatives considered**:

- *Deixar `stack` sempre vazio por compatibilidade.* Rejeitada: não há cliente
  para ser compatível, e nenhum documento vivo tem pilha cheia (D13).

---

## D5. A cascata perde o braço da pilha

**Decision**: em `round_cycle.py`,

- `MatchPhase.STACK_RESOLUTION` sai de `match_state.py`
- `_exit_action_phase`: dois passes seguidos → `ROUND_END`, e só isso
- `_AUTOMATIC_PHASES = frozenset({MatchPhase.ROUND_END, MatchPhase.UPKEEP})`
- `_run_automatic_phase`: `ROUND_END` → `end_round`; senão `run_upkeep`
- `_settle` e `_run_automatic_phase` perdem o parâmetro `catalog`, que só
  existia para `resolve_stack`
- `stack_resolution.py` é apagado

**Rationale**: FR-013 e FR-018. O laço de `_settle` continua laço — o docstring
dele já registra por quê —, e agora termina em no máximo uma volta completa:
`ROUND_END` leva a `UPKEEP`, que leva a `ACTION`.

**Alternatives considered**:

- *Manter `catalog` em `_settle` "para o próximo braço".* Rejeitada: parâmetro
  sem uso é a mesma coisa que campo sempre vazio.

---

## D6. O que vai junto com `stack_resolution.py`

**Decision**: saem sem substituto a revalidação de alvo por identificador, o
fizzle, a devolução de prioridade a quem iniciou a pilha, e a regra de que nada
abaixo do feitiço que encerrou a partida resolve.

Continuam, porque têm outros usuários:

- `Match.bank_unit()` — usado por `spell_cast_guards.py`, `blocker_pairing.py` e
  `combat_damage.py`. O docstring deixa de citar o fizzle e passa a citar o
  bloqueador órfão da §7.3, que é o `None` normal que sobrou.
- O `return` da partida terminada em `combat_cleanup._leave_combat`. O docstring
  cita `stack_resolution._reopen_action_phase` como gêmeo, e perde a citação.

**Rationale**: FR-010 e FR-020.

---

## D7. Declarar ataque com cinco guardas

**Decision**: saem `StackIsNotEmptyError`, `_ensure_stack_is_empty` e a chamada
em `declare_attack`. As guardas são renumeradas 1 a 5 no docstring do módulo.
`StackIsNotEmptyError` sai do `__all__` de `engine/__init__.py`.

**Rationale**: FR-014 e FR-019.

---

## D8. Quem fica com a vez

**Decision**: `_pass_priority` não muda de código. Muda a tabela que ele lê:

| Ação | Fases | `keeps_priority` |
|---|---|---|
| `PlayUnitAction` | ACTION | `False` |
| `DeclareAttackAction` | ACTION | `False` |
| `PassAction` | ACTION | `False` |
| `CastSpellAction` | ACTION, COMBAT | **`True`** |
| `AssignBlockerAction` | COMBAT | `True` |
| `RemoveBlockerAction` | COMBAT | `True` |
| `EndDefenseWindowAction` | COMBAT | `True` |

O docstring de `_pass_priority` deixa de dizer "a única exceção à alternância
em todo o jogo" e passa a dizer as duas: o feitiço, em qualquer fase, e a janela
do defensor.

`test_blocker_pairing.py::test_every_action_phase_arm_gives_the_turn_back`
afirma hoje `not CastSpellAction.keeps_priority`. Vira dois testes: as três
ações que devolvem, e o feitiço que fica.

**Rationale**: FR-008 e FR-008a. O que protege contra o vazamento continua sendo
a declaração explícita em cada braço, sem default.

---

## D9. Feitiço que termina a partida na Fase de Ação

**Decision**: nenhum código novo. Verificado o caminho:

1. `apply_spell_effect` → `change_nexus` → `check_victory` → `FINISHED`
2. `cast_spell` põe a carta no cemitério e zera os passes
3. `_pass_priority` retorna (`keeps_priority`)
4. `_exit_action_phase` fica inerte (passes em 0)
5. `_settle` para: `FINISHED` não é automática

É o mesmo caminho do feitiço do defensor que termina a partida hoje, que a
feature 007 testa em `test_a_defender_who_kills_themselves_freezes_the_combat`.

**Rationale**: FR-012. **Nenhum teste novo** afirma esse caminho: o único
feitiço que chega lá é o SACRIFICIAL FIRE, e a segunda correção da nota
(2026-09-11, §10 e §14) diz que ele para em Nexus 1 e só é jogado na
declaração. Os dois testes da feature 007 que o exercitam são **movidos sem
mudança** para `test_spell_in_combat.py`, trocando só o nome da ação, com
docstring apontando que a feature da §14 os reescreve — eles cobrem o `return`
de `combat_cleanup._leave_combat`, que continua existindo e que a desistência
da §10 vai precisar.

## D9a. A segunda correção da nota

**Decision**: fora desta feature. Os testes novos e reescritos aqui não usam o
SACRIFICIAL FIRE nem afirmam a duração da MAGIC BARRIER. Onde um teste existente
precisa do FIRE para produzir estado (o `AttackModifier` de
`test_spell_state_round_trip.py`), ele fica, com comentário dizendo que a feature
da §14 muda o momento do lançamento. O jogador automático de
`test_full_match.py` não joga FIRE, e o deck montado não o inclui.
`test_both_phases_give_the_same_state` perde o FIRE do laço: pela §14 o defensor
não pode jogá-lo.

**Rationale**: a correção chegou no meio da implementação desta feature. Tirar a
pilha é pedido pelas duas correções igualmente; o resto (§4, §7.1, §10, §14,
§15) é regra nova com testes próprios, e misturá-la aqui faria um corte grande
ficar enorme.

---

## D10. Os comentários que afirmam a pilha

**Decision**: reescritos para a regra corrigida, mantendo a razão quando ela
sobrevive:

| Arquivo | O que diz hoje | Vira |
|---|---|---|
| `engine/__init__.py` | "a pilha de feitiços da §6 com os cinco efeitos" | "o feitiço imediato da §5B com os cinco efeitos" |
| `engine/action_kind.py` | "quatro da §5 e quatro da §7.2" | três da §5, o feitiço das duas fases, três da §7.2 |
| `engine/combat_action.py` | "as quatro ações da janela"; cita `cast_combat_spell.py` | três; o feitiço da janela é `CastSpellAction` |
| `engine/player_action.py` | `CastSpellAction` "é outra ação"; cita `StackEntry` | a ação única das duas fases |
| `engine/round_cycle.py` | braço da pilha em `_exit_action_phase`, `_settle`, módulo | cascata de Fim de Rodada e Upkeep |
| `engine/spell_cast_guards.py` | "a §5B, que empilha"; "Não é fizzle" | um caminho; alvo fora de campo é sempre recusa |
| `engine/spell_effect.py` | "a Resolução de Pilha chama isto"; "decidir isso é da pilha" | quem chama é `cast_spell`, com o alvo já validado |
| `engine/declare_attack.py` | "3. a pilha está vazia" | cinco guardas |
| `engine/play_unit.py` | "Não usa a pilha"; "com pilha e alvo" | "resolve na hora"; "com alvo" |
| `engine/round_end.py` | "senão a feature de pilha teria de voltar aqui" | "senão a feature de feitiço teria de voltar aqui" |
| `engine/card_draw.py` | "mão, banco e pilha" | "mão e banco" |
| `engine/unit_damage.py` | "não fizzla" | "é aceito e não faz nada" |
| `engine/combat_cleanup.py` | gêmeo de `_reopen_action_phase` | a razão, sem o gêmeo |
| `engine/deck_reset.py` | "as duas pilhas de carta" | "os dois montes de carta" |
| `match/match_state.py` | `bank_unit` "autoriza o fizzle"; comentário de `stack` | o bloqueador órfão; o campo sai |
| `match/cards_in_play.py` | "dentro de uma entrada da pilha" | sai |
| `match/combat_state.py` | "como a pilha em `spell_stack.py`"; "decisão de `StackEntry`" | a razão do identificador, sem o paralelo |
| `match/serialization.py` | "ordem da pilha" | sai |
| `match/player_view.py` | "fato revelado, como a pilha" | "fato revelado, como o cemitério" |

"Pilha" no sentido de monte de cartas (`deck_reset.py`, "pilha de compra" em
dois testes) vira "monte". Não é erro de regra, mas deixa a busca do quickstart
exata: nenhuma ocorrência de `pilha`, `stack`, `fizzl` ou `empilh` sobra em
`server/apps/game`.

**Rationale**: FR-021, e a atenção registrada no Constitution Check.

**Alternatives considered**:

- *Apagar os comentários.* Rejeitada: a constituição manda preservar, e a
  maioria carrega uma razão que sobrevive à correção.
- *Deixar "pilha de compra".* Rejeitada: a busca de verificação teria que
  distinguir sentido, e busca que depende de leitura humana não é verificação.

---

## D11. O inventário dos testes

**Apagados**

| Arquivo | Por quê |
|---|---|
| `test_stack_resolution.py` (693) | Todo teste é da §6 removida. |
| `test_spell_stack.py` (140) | Testa `StackEntry`. |

**Redistribuídos: `test_cast_spell.py` (559) e `test_cast_combat_spell.py` (578)
viram três**

| Arquivo novo | Conteúdo | Origem |
|---|---|---|
| `test_cast_spell.py` | Lançamento aceito nas duas fases: efeito na hora, carta no cemitério depois do efeito, energia, energia exata, prioridade fica, segundo feitiço aceito, unidade depois do feitiço devolve a vez, passes zerados e passe seguinte não fecha a rodada, feitiço sem alvo, alvo inimigo, lado do oponente intocado, SOMEONE'S SHIELD aplica o modificador na hora, `test_both_phases_give_the_same_state` (sem SACRIFICIAL FIRE, D9a). | aceitos dos dois arquivos |
| `test_cast_spell_refusals.py` | As recusas, sem duplicata: sem alvo quando exige, alvo quando não aceita, lado errado nos dois sentidos, fora de campo, carta na mão como alvo, energia, fora da mão, carta do oponente, carta de unidade, sem prioridade primeiro, fase proibida, atacante na janela, recusa não avança contadores. | recusas dos dois arquivos |
| `test_spell_in_combat.py` | O que o feitiço do defensor muda no combate: bloqueador com buff sobrevive, bloqueador imune, atacante morto deixa bloqueador órfão, todos os atacantes mortos, dois feitiços na mesma janela, prioridade fica com o defensor, partida que acaba dentro da janela e o combate congelado ida e volta. | seções "O que o feitiço muda no dano" e "A partida que acaba dentro da janela" de `test_cast_combat_spell.py` |

Somem sem herdeiro: `test_the_spell_lands_on_top_of_the_stack`,
`test_the_effect_does_not_happen_yet`, `test_the_entry_records_the_caster`,
`test_the_entry_records_the_target_identifier`,
`test_an_untargeted_spell_records_no_target`,
`test_the_priority_passes_to_the_opponent` (a regra inverteu; o herdeiro afirma o
contrário), `test_a_refusal_leaves_the_stack_alone` (coberto por "recusa não
avança contadores" com o snapshot inteiro), `test_the_stack_stays_empty`.

`_apply_by_stack` e `_apply_by_combat` viram `_apply_in_action_phase` e
`_apply_in_combat`, os dois pela mesma ação.

**Reescritos em parte**

| Arquivo | O que muda |
|---|---|
| `test_spell_state_round_trip.py` | `played_out_match` joga os feitiços e eles já resolvem; sai `test_a_full_stack_survives_the_round_trip`; `test_a_stacked_match_is_stable_across_the_round_trip` vira `test_a_match_after_spells_is_stable_across_the_round_trip`; `test_the_three_modifier_kinds_survive_the_round_trip` não passa mais a vez para resolver. |
| `test_full_match.py` | Deck com feitiço (D12); o jogador automático joga feitiço; `_can_attack` perde `not match.stack`; teste novo afirma feitiço aceito nas duas fases; docstring. |
| `test_round_cycle.py` | Sai a seção "A costura da pilha" (dois testes) e o docstring que a explica; entra `test_two_passes_after_a_spell_close_the_round`. |
| `test_declare_attack.py` | Sai `test_a_full_stack_is_refused_naming_the_size` e os imports; entra `test_spells_then_an_attack_in_the_same_turn`; docstrings. |

**Editados em poucas linhas**

| Arquivo | O que muda |
|---|---|
| `test_blocker_pairing.py` | D8: `CastSpellAction.keeps_priority` passa a ser afirmado `True`, num teste próprio. |
| `test_combat_cleanup.py` | `test_the_stack_path_works_again_after_the_combat` vira `test_a_unit_after_the_combat_gives_the_turn_back`; dois docstrings. |
| `test_combat_damage.py` | docstring cita `resolve_stack`. |
| `test_match_serialization.py` | Saem `test_stack_order_is_preserved` e os dois de alvo na pilha; entra `test_the_document_has_no_stack_key`; docstrings. |
| `fake_match_state.py` | Sai `_fill_stack` e o import. |
| `test_match_state.py` | Inventário de fases sem `stack_resolution`; sai `test_new_match_has_an_empty_stack`. |
| `test_match_store.py` | `test_card_identity_survives_the_round_trip` pergunta por uma unidade do banco em vez do alvo da pilha; docstring. |
| `test_card_instance_identity.py` | Quatro zonas, não cinco; `_all_identifiers` sem pilha. |
| `test_match_setup.py` | Sai `assert match.stack == []`. |
| `test_play_unit.py` | Sai `test_playing_a_unit_does_not_use_the_stack`. |
| `test_player_action.py` | `STACK_RESOLUTION` sai do parametrize. |
| `test_player_view.py` | Sai `test_the_stack_appears_in_order`; entra `test_the_view_has_no_stack_key`; "pilha de compra" → "monte de compra". |
| `test_spell_effect.py` | Docstrings que citam a pilha e `test_stack_resolution.py`. |
| `test_spell_effects.py` | Sai `test_target_properties_read_the_same_twice` — as duas leituras eram lançamento e resolução, e só existe uma. |
| `test_card_draw.py`, `test_round_end.py`, `test_setup_randomness.py` | Docstrings. |
| `fake_combat_board.py`, `fake_spell_board.py` | Docstrings. |

**Rationale**: FR-022 a FR-025 ficam cobertos pelos testes que não mudam de
afirmação: `test_spell_effect.py` (os cinco efeitos direto no aplicador),
`test_combat_damage.py`, `test_combat_cleanup.py`, `test_upkeep.py`,
`test_round_end.py`, `test_card_draw.py`, `test_mulligan.py`,
`test_victory.py`.

---

## D12. Uma partida completa com feitiço de verdade

**Decision**: `test_full_match.py` monta um deck válido com feitiço — as cinco
cartas de feitiço menos o SACRIFICIAL FIRE (D9a), com 3 cópias cada (12), e unidades baratas do catálogo até 40
—, e o jogador automático, na sua vez, joga primeiro o feitiço mais barato que
tiver alvo válido, depois unidade, ataque ou passe. No Combate, o defensor joga
um feitiço se puder, e depois encerra a janela.

`play_until_over` passa a registrar `(fase antes da ação, espécie da ação)`, e
um teste novo afirma que houve `CastSpellAction` aceito em `ACTION` **e** em
`COMBAT`.

**Rationale**: o deck de andaime pega 3 cópias de cada carta em ordem de
`card_id` até fechar 40. As unidades têm os `card_id` baixos e os feitiços
começam em 1001, então **o deck de andaime não tem feitiço nenhum**, e o
`test_full_match.py` de hoje nunca jogou um. Sem esta mudança, SC-002 passaria
sem provar nada.

O laço termina: todo feitiço do MVP custa pelo menos 2 de energia, então uma vez
tem um número finito de feitiços.

**Alternatives considered**:

- *Mudar `starter_deck` para incluir feitiço.* Rejeitada: é andaime do
  matchmaking, com contrato próprio (feature 003), e esta feature não é sobre
  ele.
- *Parâmetro de deck em `fake_match_in_action_phase`.* Aceitável, e é o que o
  `/speckit-tasks` deve preferir se o deck for usado em mais de um arquivo.
  Hoje é um só.

---

## D13. Partidas gravadas antes desta feature

**Decision**: nenhuma migração, nenhum código de compatibilidade.

**Rationale**: o matchmaking grava a partida parada no mulligan, e nenhum
cliente consegue enviar jogada até a feature 009. Então todo documento vivo tem
`stack: []` e fase `mulligan`. `match_from_document` lê as chaves pelo nome e
ignora `stack`; a próxima escrita sai sem ela. O TTL é 6 horas.

---

## D14. A spec da feature 009

**Decision**: não é tocada nesta feature. Está pausada no branch
`009-match-protocol`, com o aviso no topo, e é revisada depois do merge desta.

**Rationale**: `contracts/removed_surface.md` lista o que a 009 precisa tirar —
é a entrega desta feature para ela.

---

## D15. Notas do vault

**Decision**: nenhuma nota nova. `Game/Fluxo de Partida.md` já foi corrigida, e
é a única nota que citava pilha.

**Rationale**: a constituição reserva nota nova para quando o dono pedir.
