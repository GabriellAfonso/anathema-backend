# Implementation Plan: Combate

**Branch**: `007-combat-phase` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-combat-phase/spec.md`

## Summary

A §7 inteira vira código, e o Fluxo de Partida fica implementado de ponta a
ponta. Seis módulos novos no `engine/`, um novo no `match/`, um campo novo no
estado — e, do lado da alternância da §5, **duas linhas**.

`declare_attack.py` é a §5C: seis guardas, depois consome o token, registra os
atacantes e põe a partida em Combate. `blocker_pairing.py` é o pareamento 1:1 da
§7.2. `cast_combat_spell.py` é o feitiço que resolve na hora, apoiado em
`spell_cast_guards.py`, que recebe de `cast_spell.py` as quatro guardas que os
dois caminhos fazem identicamente. `combat_damage.py` é a §7.3 e
`combat_cleanup.py` é a §7.4 e a §7.5. `match/combat_state.py` é o que a partida
lembra enquanto o combate dura.

Quatro decisões carregam a feature.

**A prioridade que não troca é propriedade da ação** (D5). Cada braço da união
declara `keeps_priority: ClassVar[bool]`, e `round_cycle._pass_priority` ganha
um `return`. Os quatro braços da §5 declaram `False`, os quatro da §7.2 declaram
`True`, e é por isso que a exceção mais perigosa desta feature **não pode**
vazar: ela não mora na função comum, mora na ação — exatamente como
`allowed_phases` já mora, pela razão que `player_action.py` já escreveu.

**O Combate não é fase automática, e mesmo assim a cascata não muda** (D6, D7).
`_AUTOMATIC_PHASES` fica como está, porque o Combate **espera** o defensor.
Declarar ataque zera os passes, como toda jogada faz, e com os passes em 0
`_exit_action_phase` fica inerte durante todo o combate. `_settle` encontra
`COMBAT` fora do conjunto e para. Quem dispara o dano, a limpeza e a volta é a
ação que encerra a janela, dentro de `_apply_action`. Nenhuma das três funções da
cascata muda uma linha.

**A apuração da §10 acontece uma vez, e `victory.py` continua sendo o único
escritor de Nexus** (D15, D16). `change_nexus_simultaneously` altera todos os
Nexus citados e chama `check_victory` depois de todos; o combate sempre cita os
**dois** jogadores, mesmo somando 0 no atacante. É o que faz FR-058 ter
correspondente literal no código, e o que torna o empate de FR-060 alcançável a
partir de um estado montado — porque jogando ele não é: nenhuma das cinco cartas
do MVP subtrai Nexus do oponente.

**Nenhum dos cinco efeitos ganha uma segunda implementação, e a prova é um teste
que não muda** (D10). As quatro guardas de lançamento sobem para
`spell_cast_guards.py`, seguindo o precedente que a feature 006 abriu ao subir
`card_in_hand` e `ensure_enough_energy` para `player_action.py`.
`test_cast_spell.py`, 559 linhas, passa **sem uma linha alterada** — é isso que
prova que o movimento foi de arquivo e não de comportamento.

O resto sustenta essas quatro. **O atacante vira espectador pela guarda de
prioridade que já existe** (D8): não há guarda nova em lugar nenhum, e as quatro
combinações de FR-022, FR-023 e FR-024 saem das duas guardas comuns da feature
005. **O pareamento é lista de pares, nunca dicionário indexado por
identificador** (D2), pela razão que `match/documents.py` já escreveu contra as
chaves de JSON. **`CombatState` não guarda quem ataca** (D3), porque o atacante é
o dono do token e uma cópia seria a segunda fonte que `PlayerState.user_id`
recusa. **Unidade que ataca ou bloqueia não sai do banco**, e é isso que faz
FR-066 valer sem código: ninguém foi movido, então ninguém precisa voltar.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova, e nenhum import novo de terceiros. Só o
que já existe: `apps.game.match` (features 002 e 006) para o estado, a
revalidação de alvo por identificador e o desfecho; `apps.game.cards` (feature
001) para `CardCatalog`, `Spell`, `Unit` e `SpellEffect`; e o próprio
`apps.game.engine` das features 005 e 006 para a forma da ação, a cascata, o
aplicador de efeito, o dano, a morte e a §10.

**Storage**: **muda**, pela segunda vez desde a feature 002. `Match` ganha
`combat: CombatState | None`; `MatchDocument` e `PlayerView` ganham a chave
`combat`. Não há migration — a partida vive no Redis como JSON, e o
compare-and-swap de `store.py` não versiona esquema, como o próprio
`MatchDocument` diz de si mesmo. A chave é obrigatória no `TypedDict` com valor
`None`, pelo argumento que a feature 006 usou para `outcome`: `total=False`
deixaria o resto do documento igualmente opcional.

**Testing**: pytest 9.1, com `cd server && pytest`. Todos os testes desta feature
são síncronos e sem I/O, inclusive o de round-trip, que passa por
`to_match_document` / `match_from_document` direto. `test_full_match.py` roda uma
partida completa do setup à vitória e afirma que nada no caminho tocou `redis`,
`channels` ou `django.db`.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`), uvicorn
com múltiplos workers. Importa aqui pela razão de sempre, e desta vez com nome:
as duas conexões de uma partida podem estar em workers diferentes, e o
pareamento de bloqueadores nasce numa ação e é lido em outra. Por isso ele é
campo do documento, e não estado de processo.

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`. Não
expõe HTTP nem websocket. Nada em `consumers/` muda.

**Performance Goals**: o caminho quente continua sendo uma ação de jogador.
Declarar ataque é uma varredura de um banco de no máximo 6 por unidade citada
(no máximo 36 comparações). Bloquear é duas buscas em listas de no máximo 6.
Encerrar a janela é uma passagem sobre no máximo 6 atacantes, cada um com um
`match.bank_unit()` (no máximo 12 unidades), seguida de uma varredura de enterro
(no máximo 12). Nada disso é sensível: o teto de banco da §12 é 6 por lado, e é
o que limita tudo.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`, sem relaxação nova em `mypy.ini`; funções de 4 a 20
linhas; arquivos abaixo de 500 linhas; nenhum campo `id` nu; nenhuma alteração
nos testes de regra das features 001 a 006; a pilha da feature 006 não é usada
nem alterada; nenhuma segunda implementação do aplicador de efeito, do dano, da
morte ou da vitória.

**Scale/Scope**: 7 módulos novos (6 em `engine/`, 1 em `match/`), 9 editados, 7
arquivos de teste novos e 1 auxiliar de teste novo. A previsão é que **nenhum
arquivo de teste existente mude** — ver D20.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | A §7 inteira de `Game/Fluxo de Partida.md` é o contrato, seção por seção: §7.1 em `declare_attack.py`, §7.2 em `blocker_pairing.py` e `cast_combat_spell.py`, §7.3 em `combat_damage.py`, §7.4 e §7.5 em `combat_cleanup.py`. A §12 dá o 1:1 estrito e o um-ataque-por-rodada. As duas perguntas que a nota não responde — ataque efetivo negativo, e partida que acaba dentro da janela — foram decididas por default explícito e registradas na spec (D12, D21), não em silêncio no código. O item da §13 sobre feitiço que invoca bloqueador fica fora de escopo, como a nota manda. Nenhuma nota nova é escrita. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | `attacker_card_instance_ids`, `blocker_card_instance_id`, `attacker_card_instance_id` no estado, no documento e na visão. Todos são `CardInstanceId`, o `NewType` que existe justamente porque três inteiros viajam nos mesmos payloads. Nenhum `id` nu em lugar nenhum. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | União fechada de oito braços, despachada por `match` exaustivo em `_apply_action` — um braço sem regra é erro de mypy. `CombatState \| None`, `BankUnit \| None`, `CardInstanceId \| None` explícitos. Os dois estreitamentos impossíveis (`Match.combat` fora do combate, `token_holder_user_id` ausente) usam recusa nomeada, nunca `assert` — que some com `-O` — nem `cast`. Nenhuma relaxação nova em `mypy.ini`. |
| IV. Unidades pequenas, uma responsabilidade | ⚠️ ATENÇÃO | Sete módulos novos, um por regra, entre 40 e 200 linhas. Mas `player_action.py` vai de 347 para ~470 linhas com os cinco braços novos. Abaixo do teto de 500, e com 30 linhas de folga. Detalhe em [Complexity Tracking](#complexity-tracking). |
| V. Comportamento testado com fakes nomeados | ✅ PASS | Nenhum I/O novo, então nenhum fake de I/O novo. `FakeCardCatalog`, `ScriptedRandomSource`, `fake_match_state.py`, `fake_setup.py` e `match_snapshot.py` cobrem quase tudo; o único acréscimo é `fake_combat_board.py`, um construtor de tabuleiro no formato de `fake_spell_board.py` — não é fake, não substitui I/O, e por isso é função e não classe. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova, nenhum bump, nenhum import de terceiros. |
| Estrutura Django previsível | ✅ PASS | Módulos dentro de pacotes que já existem. Sem app novo, sem `INSTALLED_APPS`, sem migration, sem URL, sem consumer. |
| Injeção de dependência | ✅ PASS | `catalog` chega por parâmetro nomeado em toda função que lê molde de carta — e **não** chega nas que não leem: `declare_attack`, `assign_blocker` e `remove_blocker` não o recebem. Nenhum módulo desta feature chama `mvp_catalog()` nem importa `random`. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy` e `black` rodam sem configuração nova. |
| Comentários preservados no refactor | ⚠️ ATENÇÃO | Seis textos existentes deixam de ser previsão e viram fato; precisam ser **reescritos**, não apagados. Detalhe abaixo. |

### O que precisa ser reescrito, e por quê

Os seis foram escritos prevendo esta feature. Nenhum está errado — todos estão
cumpridos, e o texto precisa passar do futuro para o presente.

1. **`engine/__init__.py`, docstring do pacote.** Hoje diz: *"O combate da §7
   cai no mesmo lugar quando entrar."* Caiu. A frase vira a lista fechada do que
   o pacote é, e o parágrafo ganha uma linha: o Fluxo de Partida está
   implementado de ponta a ponta. O comentário sobre `apply_spell_effect` —
   *"o mesmo aplicador que o combate da §7.2 vai usar"* — perde o "vai".

2. **`engine/player_action.py`, docstring do módulo.** Hoje diz: *"Declarar
   ataque entra igual."* Entrou, e com ele os quatro braços da janela. O texto
   ganha o que `keeps_priority` é e por que ela mora na ação — o mesmo argumento
   que o módulo já faz para `allowed_phases`.

3. **`engine/player_action.py`, docstring de `ActionKind`.** Hoje diz:
   *"Conjunto fechado. A ação que falta da §5 — declarar ataque — entra aqui
   junto com o braço dela."* Entrou, e a lista agora fecha de verdade: quatro
   ações da §5 e quatro da §7.2, e o Fluxo de Partida não tem uma nona.

4. **`engine/player_action.py`, docstring de `CastSpellAction`.** Hoje diz:
   *"`{ACTION}` e não `{ACTION, COMBAT}`: o feitiço do defensor da §7.2 resolve
   imediatamente (...) e é outra ação — não esta com uma fase a mais."* A outra
   ação existe; o texto passa a apontar para `CastCombatSpellAction` pelo nome.

5. **`engine/unit_vitals.py`, últimos parágrafos.** Hoje diz que
   `unit_effective_attack` *"não mora aqui ainda"* e que ela *"entra com o
   combate"*. Entrou. O texto sai e a função ocupa o lugar. O parágrafo de
   abertura, que separa este módulo de `unit_damage.py` por "a conta de vida
   muda com palavras-chave, o efeito do dano muda com o combate", ganha a
   correção: o combate chegou, e o efeito do dano **não** mudou —
   `deal_damage_to_unit` não foi tocado.

6. **`match/match_state.py`, docstring de `MatchPhase`.** Hoje diz: *"`COMBAT`
   existe desde já, mas o estado que o combate precisa — o pareamento de
   bloqueadores da §7.2 — entra na feature de combate."* Entrou. A frase vira a
   descrição do que `COMBAT` é: a única fase não automática além da Fase de Ação,
   e a única em que a prioridade não troca.

Cinco textos existentes passam a ser verificáveis por esta feature, e é bom que
**não** mudem:

- **`engine/unit_damage.py`, `bury_dead_units`**: *"o dano da §7.3 é simultâneo:
  o combate vai matar várias unidades dos dois lados num evento só, e esta é a
  forma que ele já precisa."* `combat_cleanup` a chama uma vez, sobre os dois
  bancos, e é a forma certa.
- **`engine/victory.py`, `check_victory`**: *"É o que permite ao combate chamá-la
  depois do dano simultâneo sem contar quantas vezes já foi chamada."* D15 usa
  exatamente essa propriedade.
- **`engine/spell_effect.py`, docstring do módulo**: *"Este módulo não sabe de
  onde a chamada veio, e não existe parâmetro que diga."* `cast_combat_spell` é
  o segundo chamador, e continua não existindo o parâmetro.
- **`match/spell_stack.py`, docstring do módulo**: *"O alvo é guardado como
  identificador, nunca como referência ao objeto."* `CombatState` herda a forma e
  a razão, e é por isso que `combat_state.py` não precisa reescrevê-la.
- **`match/cards_in_play.py`, `BankUnit`**: *"Uma unidade em campo. Existe só
  enquanto está no banco."* Continua verdade **durante o combate** — não existe
  zona de combate, e é isso que faz FR-066 valer sem código.

### Reverificação depois da Fase 1

O desenho fechado não mudou nenhum veredito. Cinco pontos que a Fase 1 tornou
concretos:

- **Princípio I**: a §7.3 não responde o que acontece quando o **bloqueador**
  some antes da resolução — só o caso do atacante. A Fase 1 precisou de um braço
  para isso, e a resposta escolhida (D14) é a que a própria §7.3 sustenta
  — "Bloqueado: nenhum dano chega ao Nexus" —, é simétrica com a regra do órfão,
  e é inalcançável com as cinco cartas do MVP. Está na spec como Edge Case, não
  escondida no código.
- **Princípio II**: `CombatState` ficou sem `attacking_user_id`. Gravá-lo seria a
  segunda fonte que `PlayerState.user_id` e `Match.awaiting_mulligan_user_ids`
  já recusam, cada um com a razão escrita no próprio docstring.
- **Princípio III**: a exaustividade do `match` de `_apply_action` é verificada
  sem `assert_never`, porque aquele `match` está dentro de uma função que
  devolve `None` — o mesmo buraco que a feature 006 encontrou em `_dispatch`. A
  Fase 1 registra que o braço `case _: assert_never(action)` entra também em
  `_apply_action`, pela mesma razão e com a mesma verificação: remover um braço e
  conferir que o mypy reprova.
- **Princípio IV**: o módulo maior depois da feature é `player_action.py`, com
  ~470 linhas. `combat_damage.py` fica em ~130 e `declare_attack.py` em ~200,
  este último porque sete recusas nomeadas custam ~15 linhas cada.
- **Princípio V**: `test_cast_combat_spell.py` prova SC-008 comparando os dois
  caminhos **campo a campo**, com `match_snapshot` dos dois estados finais a
  partir do mesmo inicial. Foi essa comparação que apontou D11 — a ordem do
  cemitério —, que nenhum requisito pede e que teria divergido em silêncio.

## Project Structure

### Documentation (this feature)

```text
specs/007-combat-phase/
├── plan.md                       # Este arquivo
├── spec.md                       # A especificação
├── research.md                   # Fase 0 — 21 decisões de desenho e alternativas
├── data-model.md                 # Fase 1 — estado novo, transições, invariantes
├── quickstart.md                 # Fase 1 — como rodar e provar que funciona
├── contracts/
│   ├── declare_attack.md         # Fase 1 — a §5C, o braço novo e as 7 recusas
│   ├── defense_window.md         # Fase 1 — a §7.2: prioridade, bloqueio, feitiço
│   └── combat_resolution.md      # Fase 1 — a §7.3, a §7.4 e a §7.5
├── checklists/
│   └── requirements.md           # Checklist de qualidade da spec (16/16)
└── tasks.md                      # Fase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
server/
└── apps/
    └── game/
        ├── match/
        │   ├── combat_state.py          # NOVO — CombatState, BlockAssignment
        │   ├── match_state.py           # EDITADO — Match.combat,
        │   │                            #   Match.ongoing_combat(),
        │   │                            #   MatchIsNotInCombatError
        │   ├── documents.py             # EDITADO — CombatDocument,
        │   │                            #   BlockAssignmentDocument,
        │   │                            #   MatchDocument["combat"]
        │   ├── serialization.py         # EDITADO — ida e volta do pareamento
        │   ├── player_view.py           # EDITADO — PlayerView["combat"]
        │   ├── __init__.py              # EDITADO — __all__
        │   ├── spell_stack.py           # NÃO TOCADO — o combate não usa a pilha
        │   ├── modifiers.py             # NÃO TOCADO — AttackModifier já basta
        │   ├── cards_in_play.py         # NÃO TOCADO — não existe zona de combate
        │   ├── match_outcome.py         # NÃO TOCADO — o empate já cabe nele
        │   └── player_state.py          # NÃO TOCADO
        ├── engine/
        │   ├── declare_attack.py        # NOVO — §5C/§7.1: declare_attack e as
        │   │                            #   7 recusas
        │   ├── blocker_pairing.py       # NOVO — §7.2: assign_blocker,
        │   │                            #   remove_blocker e as 5 recusas
        │   ├── spell_cast_guards.py     # NOVO — as 4 guardas da §5B, que os
        │   │                            #   dois caminhos compartilham
        │   ├── cast_combat_spell.py     # NOVO — §7.2: o feitiço imediato
        │   ├── combat_damage.py         # NOVO — §7.3: resolve_combat_damage
        │   ├── combat_cleanup.py        # NOVO — §7.4/§7.5: end_combat
        │   ├── player_action.py         # EDITADO — 5 braços novos,
        │   │                            #   keeps_priority, ActionKind
        │   ├── round_cycle.py           # EDITADO — 5 braços em _apply_action,
        │   │                            #   o return de _pass_priority
        │   ├── cast_spell.py            # EDITADO — encolhe para a regra da §5B
        │   ├── unit_vitals.py           # EDITADO — unit_effective_attack
        │   ├── victory.py               # EDITADO — change_nexus_simultaneously
        │   ├── stack_resolution.py      # EDITADO — só o import que mudou de
        │   │                            #   módulo
        │   ├── __init__.py              # EDITADO — __all__ e docstring
        │   ├── spell_effect.py          # NÃO TOCADO — é a prova de FR-038
        │   ├── unit_damage.py           # NÃO TOCADO — é a prova de FR-056/FR-064
        │   ├── round_end.py             # NÃO TOCADO
        │   ├── upkeep.py                # NÃO TOCADO
        │   ├── play_unit.py             # NÃO TOCADO
        │   ├── card_draw.py             # NÃO TOCADO
        │   └── match_setup.py           # NÃO TOCADO
        ├── cards/                       # NÃO TOCADO — nenhuma carta nova
        ├── consumers/                   # NÃO TOCADO — transporte está fora de escopo
        └── tests/
            ├── test_declare_attack.py           # NOVO — US1
            ├── test_blocker_pairing.py          # NOVO — US2
            ├── test_cast_combat_spell.py        # NOVO — US3
            ├── test_combat_damage.py            # NOVO — US4
            ├── test_combat_cleanup.py           # NOVO — US5, US6
            ├── test_combat_state_round_trip.py  # NOVO — US7
            ├── test_full_match.py               # NOVO — US8
            ├── fake_combat_board.py             # NOVO — tabuleiro de combate
            ├── match_snapshot.py                # reaproveitado, não alterado
            ├── fake_spell_board.py              # reaproveitado, não alterado
            ├── fake_setup.py                    # reaproveitado, não alterado
            ├── test_cast_spell.py               # NÃO TOCADO — é a prova de D10
            ├── test_spell_effect.py             # NÃO TOCADO — é a prova de FR-038
            ├── test_unit_damage.py              # NÃO TOCADO
            ├── test_victory.py                  # NÃO TOCADO
            ├── test_stack_resolution.py         # NÃO TOCADO
            ├── test_action_phase.py             # NÃO TOCADO — é a prova de FR-021
            ├── test_round_cycle.py              # NÃO TOCADO
            └── test_player_action.py            # NÃO TOCADO
```

**Structure Decision**: nenhum pacote novo. `engine/` continua plano, com um
módulo por regra, e a feature acrescenta seis. A razão de não juntá-los está em
[research.md D18](./research.md): cada um tem uma razão própria para mudar, e o
grafo entre eles continua sendo um DAG raso.

```
round_cycle ──┬──> declare_attack ──────> player_action
              │
              ├──> blocker_pairing ─────> (match: CombatState)
              │
              ├──> cast_spell ──────────┐
              │                         ├──> spell_cast_guards
              ├──> cast_combat_spell ───┘         │
              │           │                       └──> (cards: Spell, TargetKind)
              │           └──> spell_effect ──> unit_damage ──> unit_vitals
              │                     │
              ├──> combat_cleanup ──┼──> combat_damage ──> unit_vitals
              │           │         │                  └──> victory
              │           └─────────┴──> unit_damage
              │
              └──> stack_resolution ──> spell_effect
```

Nenhum ciclo. `victory.py` não importa `spell_effect.py` nem `combat_damage.py`;
`unit_vitals.py` continua não importando nada de `engine/`. Cada camada é
testável sem a de cima, e `combat_damage.py` é testável sem `combat_cleanup.py`.

`match/` **é** tocado, como na feature 006 e pelo mesmo motivo: a feature
acrescenta estado que não existia. O acréscimo é mínimo e desenhado para não
mexer em teste nenhum — um módulo, um campo com default, um método de
estreitamento, duas chaves de documento e uma de visão (D19, D20).

`spell_effect.py` e `unit_damage.py` **não** são tocados, e isso é o centro da
feature, não detalhe: são eles que FR-038, FR-056, FR-064 e FR-083 proíbem
duplicar. Que os dois apareçam na coluna "NÃO TOCADO" é a forma mais curta de
verificar esses quatro requisitos.

`round_end.py` também não é tocado. O bônus de ataque que o combate lê carrega a
duração que o efeito declara desde a feature 006, e a varredura da §8 já sabe o
que fazer com ela.

`consumers/` não é tocado. Quem chama `submit_action` com uma
`DeclareAttackAction` é a feature de transporte, e a spec a põe fora de escopo.

## Complexity Tracking

Uma tensão de princípio a justificar, e sete pontos que esta feature toca e
resolve ou registra.

| Ponto | O que é | Encaminhamento |
|---|---|---|
| **`player_action.py` com ~470 linhas** | O módulo cresce 35% com os cinco braços novos e fica a 30 linhas do teto de 500. | **Aceito, com três razões** (D4). A responsabilidade não mudou — o docstring dele diz "a forma de uma jogada que entra no motor, e o que ela precisa provar", e oito braços continuam sendo isso. As **recusas** de cada regra nova ficam no módulo da regra, como `BankIsFullError` já fica em `play_unit.py`; é isso que segura o arquivo. E não existe um nono braço: a §5 tem quatro ações e a §7.2 tem quatro, e o Fluxo de Partida não tem outra em lugar nenhum. A alternativa — partir em três módulos, um deles só para o enum, porque a união e os braços dariam ciclo de import — troca um arquivo de 470 linhas por três arquivos e um problema de dependência. |
| O empate do combate é inalcançável jogando | FR-060 pede empate por dano de combate, e nenhuma das cinco cartas do MVP subtrai Nexus do oponente. | **Registrado na spec, e resolvido estruturalmente** (D16). `resolve_combat_damage` cita os **dois** jogadores na apuração, sempre, mesmo somando 0 no atacante. O cenário é exercido a partir de um estado montado, e o teste pega a escolha errada entre `change_nexus` e `change_nexus_simultaneously` — que é o bug que a spec avisou que nenhum teste de um jogador só pega. |
| O bloqueador que some antes da resolução | A §7.3 define o atacante que some (órfão), não o bloqueador. | **Braço escrito, resposta justificada, caso inalcançável** (D14). O par só troca dano com os dois em campo, e o atacante continua bloqueado — "Bloqueado: nenhum dano chega ao Nexus" é propriedade da declaração. Simétrico com a regra do órfão. Não alcançável com as cinco cartas: o atacante é espectador e nenhum feitiço do defensor mata unidade do próprio dono. |
| Um `CombatState` sobrevivendo num estado terminal | FR-062 congela o combate interrompido, e a invariante `phase is COMBAT ⟺ combat is not None` deixaria de valer. | **A invariante é unidirecional de propósito** (D17). Vale `phase is COMBAT ⟹ combat is not None`. O `CombatState` que sobrevive é exatamente o do combate que **nunca resolveu**, e é a única coisa que distingue esse caso de um combate resolvido. Limpar para manter a bicondicional apagaria essa distinção num estado que a spec manda preservar. |
| Dois escritores do par `(combat, phase)` | `declare_attack._enter_combat` escreve, `combat_cleanup._leave_combat` apaga. `_finish_match` da feature 006 tinha um só. | **Aceito**: são duas transições opostas de um sub-estado que tem entrada e saída, ao contrário de `FINISHED`, que é terminal e por isso pode ter um escritor só. Cada um escreve o par inteiro e é privado do módulo da sua transição, e a invariante I1 é afirmada por teste nos dois lados. |
| O piso em 0 do ataque efetivo | Nenhuma carta do MVP produz bônus negativo, e o piso existe para um caso que não acontece. | **Escrito assim mesmo** (D12). Sem ele, um ataque negativo curaria a unidade e somaria Nexus — duas regras que a §7 não tem. O modificador de ataque aceita negativo por construção, e a palavra-chave de redução de ataque está na §13. O piso fica no ataque efetivo, não em `deal_damage_to_unit`, para não escrever uma regra da §7.3 no caminho da §5B. |
| `cast_spell.py` refatorado por uma feature que não é a dele | As cinco recusas e as quatro guardas mudam de arquivo. | **Aceito, com a prova amarrada** (D10). É o precedente que a feature 006 abriu ao subir `card_in_hand` e `ensure_enough_energy`, e o que FR-040 exige. A prova é que `test_cast_spell.py` — 559 linhas — passa **sem uma linha alterada**. Se ele precisar mudar, o movimento não foi só de arquivo, e a tarefa volta. |
| `unit_has_damage_immunity` com a razão ligeiramente errada | O docstring dela diz que mora entre as consultas porque *"o combate vai fazê-la sem causar dano nenhum, ao decidir bloqueio"*. O combate não a consulta ao decidir bloqueio. | **Corrigido na reescrita.** Quem a consulta é `deal_damage_to_unit`, e o combate herda a imunidade de graça — FR-055 vale sem uma linha nova. O lugar dela está certo; a frase que o justifica é que precisa passar a ser a verdadeira. |

### O que a implementação corrigiu no plano

Quatro previsões da Fase 1 que a execução mudou. Nenhuma altera requisito nem
cenário de aceitação.

| Previsão | O que aconteceu | Encaminhamento |
|---|---|---|
| `player_action.py` fica em ~470 linhas, abaixo do teto | Ficou em **518** depois do `black`. Os docstrings dos cinco braços novos saíram mais longos que o estimado. | **Dividido em três**, exatamente como [research D4](./research.md) descreveu a alternativa recusada: `action_kind.py` (27 linhas, o discriminante que os dois lados precisam), `player_action.py` (409, os quatro braços da §5 mais as guardas comuns e a união) e `combat_action.py` (125, os quatro braços da §7.2). O argumento contra o split era "está abaixo do teto"; a premissa caiu, e com ela o argumento. O ciclo de import que D4 temia não existe porque `ActionKind` saiu para o terceiro módulo. |
| 7 arquivos de teste novos | São **8**. | `test_combat_state.py` entrou na Fase 2: `CombatState`, as três consultas e `ongoing_combat()` são funções novas, e o princípio V exige teste para cada uma. Pô-las em `test_match_state.py` quebraria a promessa de não tocar teste existente. Já estava registrado em [tasks.md](./tasks.md). |
| O docstring de `check_victory` não muda | **Mudou.** A frase "é o que permite ao combate chamá-la depois do dano simultâneo" ficou falsa: o combate **não** a chama direto, chama `change_nexus_simultaneously`, que a chama uma vez. | Reescrito para o que a idempotência de fato garante — e para o que ela **custa**: é ela que torna a escolha errada entre as duas portas silenciosa, porque a segunda apuração não desfaz a primeira. Os outros quatro textos da lista "não devem mudar" continuam idênticos. |
| O teste de fronteira olha `engine/` e `match/` | `match/store.py` e `match/client.py` importam Redis, e devem. | O teste passou a olhar **só** o `engine/`, com a razão escrita nele: aqueles dois módulos são o embrulho do Redis que a feature 003 entregou, e é o chamador que grava por eles. |

**Resultado**: 707 testes verdes (568 antes da feature), `mypy` limpo em 154
arquivos sob `strict`, `black` limpo, e **nenhum arquivo de teste das features
001 a 006 alterado** — a previsão de [research D20](./research.md) valeu inteira.

**Registro no vault**: nada novo para `Backend/TODO.md`. O timeout da janela do
defensor continua em aberto na §13 do Fluxo de Partida, é problema de
transporte, e a spec o põe fora de escopo por decisão — não por dívida desta
feature. A pergunta da §13 sobre feitiço que invoca bloqueador no mesmo combate
continua onde está, e nenhum dos cinco feitiços do MVP a torna alcançável.

**Nenhuma correção na spec.** A Fase 1 não encontrou requisito ambíguo nem
cenário impossível: os dois casos que precisavam de decisão (o bloqueador
ausente e a partida terminada na janela) já estavam nos Edge Cases e nas
Assumptions da spec, escritos antes do plano.
