# Implementation Plan: Feitiço imediato

**Branch**: `008-instant-spells` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-instant-spells/spec.md`

## Summary

A pilha da feature 006 sai do motor, e o feitiço passa a funcionar como o
Fluxo de Partida corrigido descreve: resolve na hora, em qualquer fase, e **não
passa a vez**.

É uma feature de remoção. O caminho certo já existe: `cast_combat_spell.py`, da
feature 007, já faz exatamente o que a §5B corrigida pede — guardas, energia,
mão, efeito, cemitério, e a prioridade fica. O trabalho é torná-lo o único
caminho, e apagar o outro.

Quatro decisões carregam a feature.

**Uma ação de feitiço, e ela declara `keeps_priority = True`** (D1). As duas
ações de hoje — `CastSpellAction`, que empilhava, e `CastCombatSpellAction`, que
resolvia — passam a ter os mesmos campos, o mesmo efeito e a mesma prioridade.
Fica uma: `CastSpellAction`, com `allowed_phases = {ACTION, COMBAT}`.
`CastCombatSpellAction` e `ActionKind.CAST_COMBAT_SPELL` somem. O
`keeps_priority` do commit 7239e48 não muda de forma — a ação declara, e
`round_cycle._pass_priority` só lê. O que muda é o que ele protege: agora são
quatro ações que ficam com a vez (o feitiço e as três da janela), e três que a
devolvem (jogar unidade, declarar ataque, passar).

**`cast_spell.py` passa a ter o corpo de `cast_combat_spell.py`** (D2), mais a
zeragem de passes que a §5B manda. `cast_combat_spell.py` e
`stack_resolution.py` são apagados, e com eles o fizzle, a devolução de
prioridade ao iniciador da pilha e a regra de partida encerrada no meio da
resolução.

**A pilha some do estado, da forma gravada, da visão e das fases** (D4, D5).
`match/spell_stack.py`, `StackEntry`, `StackEntryDocument`, `Match.stack`, a
chave `stack` do documento e da visão, e `MatchPhase.STACK_RESOLUTION`. A
cascata de `round_cycle` perde um braço: as fases automáticas voltam a ser
`ROUND_END` e `UPKEEP`, que é o que a feature 005 tinha antes da 006.

**Declarar ataque perde a terceira guarda** (D7). `StackIsNotEmptyError` sai do
motor e do `__all__`.

Nenhum dos cinco efeitos muda. O aplicador `spell_effect.py`, as guardas de
`spell_cast_guards.py`, a varredura de morte, a §10, o combate e a cascata de
Fim de Rodada ficam onde estão, e o comportamento deles é o que o caminho do
defensor já tinha.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova, e nenhum import novo. Só o que já existe
em `apps.game.match`, `apps.game.cards` e `apps.game.engine`.

**Storage**: **muda**, removendo. `MatchDocument` perde a chave `stack`. Não há
migration: a partida vive no Redis como JSON, `match_from_document` lê as chaves
pelo nome, então um documento antigo com `stack` é lido sem erro e a próxima
escrita já sai sem ela. Nenhum documento vivo pode ter pilha cheia ou fase
`stack_resolution` — nenhum cliente consegue jogar até a feature 009 (D13).

**Testing**: pytest 9.1, com `cd server && pytest`. Tudo síncrono e sem I/O,
como nas features 005 a 007, exceto `test_match_store.py`, que já usa o fake de
Redis e só troca o que pergunta.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`), uvicorn
com múltiplos workers. Não muda nada aqui: a forma gravada fica menor, e é a
mesma entre workers.

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`.
Nada em `consumers/` muda.

**Performance Goals**: jogar feitiço fica mais barato que hoje — a resolução
acontece na mesma chamada, sem uma passagem posterior pela pilha. Os limites
continuam os da §12: banco de 6 por lado.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`, sem relaxação nova; funções de 4 a 20 linhas;
arquivos abaixo de 500 linhas; nenhum `id` nu; nenhuma segunda implementação do
aplicador de efeito, das guardas, do dano, da morte ou da vitória; o
`_apply_action` continua com `match` exaustivo e `assert_never`.

**Scale/Scope**: 3 módulos de produção apagados, 1 reescrito, 21 editados (a
maioria só docstring). 2 arquivos de teste apagados, 2 redistribuídos em três,
4 reescritos em parte, 19 editados em poucas linhas. Inventário completo em
[research.md, D11](./research.md#d11-o-inventário-dos-testes).

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | É o princípio que dispara a feature: a nota `Game/Fluxo de Partida.md` foi corrigida em 2026-09-11, e o código diverge dela. A constituição diz que nesse caso o código está errado. §5 Alternância, §5B, §5C, saída da §5, §6 removida e §7.2 são o contrato, e cada uma tem destino no código (D1, D2, D5, D7). Nenhuma nota nova é escrita. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | Nenhum campo novo. `card_instance_id` e `target_card_instance_id` da ação única são os que as duas ações já tinham. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | A união fechada perde um braço, e o `match` exaustivo de `_apply_action` com `assert_never` é o que garante que nenhum caso ficou para trás. `validated_spell_cast` passa a receber `CastSpellAction` em vez de dois identificadores soltos (D3) — o motivo dos soltos era haver dois tipos de ação. Nenhuma relaxação nova. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | Todo arquivo de produção **diminui**. `test_cast_spell.py` (559) e `test_cast_combat_spell.py` (578) não viram um arquivo de 1100 linhas: viram três, por responsabilidade (D11). |
| V. Comportamento testado com fakes nomeados | ✅ PASS | Nenhum I/O novo. `fake_spell_board.py` e `fake_combat_board.py` continuam servindo; `fake_match_state.py` perde `_fill_stack`. A partida completa com feitiço precisa de um deck com feitiço, e ele é montado no próprio teste a partir do catálogo (D12). |
| Stack fixada | ✅ PASS | Nenhuma dependência nova. |
| Estrutura Django previsível | ✅ PASS | Nenhum módulo novo de produção. Sem app, sem migration, sem URL, sem consumer. |
| Injeção de dependência | ✅ PASS | `catalog` sai de `_settle` e `_run_automatic_phase`, que só o recebiam para `resolve_stack`. Continua em `submit_action`, que o repassa às ações. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy` e `black` sem configuração nova. |
| Comentários preservados no refactor | ⚠️ ATENÇÃO | Cerca de vinte textos existentes afirmam a pilha como regra. A constituição manda preservar comentários, e eles carregam intenção — mas um comentário que afirma regra removida é o erro que esta feature corrige (FR-021). Eles são **reescritos** para a regra corrigida, mantendo a razão que carregavam quando a razão sobrevive. Lista em [research.md, D10](./research.md#d10-os-comentários-que-afirmam-a-pilha). |

**Resultado**: PASS, com uma atenção registrada e justificada. Nenhuma violação
exige entrada em Complexity Tracking.

### Re-verificação depois da Fase 1

O desenho não acrescentou módulo, dependência, relaxação de tipo nem
indireção. Os contratos em `contracts/` só descrevem superfície que diminui ou
que já existia. A atenção de comentários continua a única, e continua
justificada. **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/008-instant-spells/
├── plan.md              # este arquivo
├── research.md          # D1–D15: as decisões e o inventário
├── data-model.md        # o estado, a ação e a prioridade depois da remoção
├── quickstart.md        # como provar que a pilha saiu e o feitiço resolve na hora
├── contracts/
│   ├── cast_spell.md     # a ação única de jogar feitiço
│   └── removed_surface.md # tudo que sai da superfície pública, para a feature 009
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks — não criado aqui
```

### Source Code (repository root)

```text
server/apps/game/
├── engine/
│   ├── __init__.py            # EDITADO: exports de CastCombatSpellAction e StackIsNotEmptyError saem; docstring
│   ├── action_kind.py         # EDITADO: CAST_COMBAT_SPELL sai; sete espécies
│   ├── cast_spell.py          # REESCRITO: o corpo de cast_combat_spell + zeragem de passes
│   ├── cast_combat_spell.py   # APAGADO
│   ├── stack_resolution.py    # APAGADO
│   ├── combat_action.py       # EDITADO: CastCombatSpellAction sai; três ações da janela
│   ├── player_action.py       # EDITADO: CastSpellAction em {ACTION, COMBAT}, keeps_priority True; união de sete
│   ├── round_cycle.py         # EDITADO: braço do combate sai; saída da §5 com um ramo; cascata sem pilha
│   ├── declare_attack.py      # EDITADO: guarda 3 e StackIsNotEmptyError saem
│   ├── spell_cast_guards.py   # EDITADO: recebe a ação; docstrings
│   ├── spell_effect.py        # docstrings
│   ├── combat_cleanup.py      # docstring
│   ├── play_unit.py           # docstrings
│   ├── round_end.py           # docstring
│   ├── card_draw.py           # docstring
│   ├── unit_damage.py         # docstring
│   └── deck_reset.py          # docstring ("pilhas de carta" -> "montes")
└── match/
    ├── __init__.py            # EDITADO: StackEntry e StackEntryDocument saem
    ├── spell_stack.py         # APAGADO
    ├── match_state.py         # EDITADO: STACK_RESOLUTION e Match.stack saem; docstring de bank_unit
    ├── documents.py           # EDITADO: StackEntryDocument e a chave stack saem
    ├── serialization.py       # EDITADO: to/from_stack_entry_document saem
    ├── player_view.py         # EDITADO: a chave stack sai
    ├── cards_in_play.py       # docstring
    └── combat_state.py        # docstring

server/apps/game/tests/        # inventário em research.md, D11
```

**Structure Decision**: nenhum módulo novo de produção. A regra corrigida já tem
casa — `cast_spell.py` é "a ação B da §5", e a §5B corrigida é o que o nome
sempre disse. Os três arquivos apagados só existiam por causa da pilha.

## Riscos e o que os cobre

| Risco | Onde apareceria | O que cobre |
|---|---|---|
| A exceção de prioridade vaza para jogar unidade, atacar ou passar | `keeps_priority` de algum braço da §5 | `test_blocker_pairing.py::test_every_action_phase_arm_gives_the_turn_back` passa a afirmar as três que devolvem e o feitiço que fica (D8) |
| Feitiço na Fase de Ação e na janela dão resultados diferentes | um `if` de fase em `cast_spell` | `test_both_phases_give_the_same_state`, herdeiro de `test_both_paths_give_the_same_state` (D11) |
| Um passe depois de feitiço fecha a rodada sem o oponente poder reagir | zeragem de passes esquecida | cenário 5 da US1, em `test_cast_spell.py` |
| Resto de pilha num comentário, teste ou nome | qualquer arquivo de `apps/game` | a busca do [quickstart](./quickstart.md) devolve zero |
| Partida completa passa sem nunca jogar feitiço | o deck de andaime não tem feitiço | `test_full_match.py` monta deck com feitiço e afirma feitiço aceito nas duas fases (D12) |

## Complexity Tracking

Nenhuma violação a justificar.
