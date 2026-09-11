# Implementation Plan: Pilha de Feitiços e Efeitos

**Branch**: `006-spell-stack-effects` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-spell-stack-effects/spec.md`

## Summary

A §5B, a §6 e a §10 do Fluxo de Partida viram código, e o motor finalmente
**altera** vida de unidade, ataque de unidade e Nexus de jogador. Seis módulos
novos no `engine/`, um novo no `match/`, e — pela primeira vez desde a feature
002 — **estado novo**: a partida agora pode acabar, e o fim é estado.

`cast_spell.py` é a §5B: quatro guardas, depois desconta energia, tira a carta
da mão e empilha, sem aplicar nada. `stack_resolution.py` é a §6: drena a pilha
inteira do topo para a base, revalida cada alvo pelo identificador, aplica ou
fizzla, e devolve a prioridade a quem **abriu** a pilha. `spell_effect.py` é o
aplicador dos cinco efeitos, apoiado em `unit_vitals.py` (as perguntas sobre
vida e imunidade), `unit_damage.py` (o dano e o enterro) e `victory.py` (a §10).
`match/match_outcome.py` é o resultado da partida.

Três decisões carregam a feature, e as outras existem para que elas fiquem como
estão.

**O fim da partida é estado, e um ponto só o escreve** (D1). `MatchPhase` ganha
`FINISHED` e `Match` ganha `outcome: MatchOutcome | None`, com a invariante
`outcome is not None ⟺ phase is FINISHED` mantida por `_finish_match()` — a
única função que escreve o par. Os dois campos existem porque respondem
perguntas com consumidores diferentes: `phase` é o que a cascata lê para parar e
o que `allowed_phases` compara para recusar; `outcome` é quem perdeu. E porque
`FINISHED` não está em `_AUTOMATIC_PHASES` nem em nenhum `allowed_phases`, a
partida terminada **para a cascata e recusa toda ação sem uma linha nova em
nenhum dos dois lugares**.

**O aplicador de efeito não sabe de onde a chamada veio, e não existe parâmetro
que diga** (D7). É FR-029 literal, e é a fronteira que decide se a feature de
combate é pequena ou se ela duplica os cinco efeitos. A revalidação de alvo fica
na pilha; o aplicador recebe o `BankUnit` já resolvido. A duração de todo
modificador criado vem de `effect.duration`, nunca de um literal — é o que faz o
Fim de Rodada varrer a imunidade e não varrer o buff de vida **sem que o
aplicador saiba o que é varrido**, e é por isso que FR-062 vale por construção.

**A pilha para no estado terminal, e quem para é o laço, não o aplicador**
(D11). O `pop` acontece antes de qualquer decisão e o cemitério depois de todos
os caminhos, então a pilha esvazia mesmo quando a partida termina no meio, sem
um segundo laço de limpeza. A parada mora no laço porque o aplicador é
compartilhado com o combate, e o combate não tem pilha: um feitiço de defensor
que encerre a partida não tem "próximo feitiço" para pular.

O resto sustenta essas três. **A ordem das guardas comuns da feature 005 não
muda** (D3): `MatchIsOverError` é subclasse de `PhaseForbidsActionError`,
levantada de dentro da terceira guarda, e não uma guarda nova antes delas.
**`card_in_hand` e `ensure_enough_energy` sobem para `player_action.py`** (D16),
seguindo o precedente que a própria feature 005 abriu ao mover
`CardNotInHandError` de `mulligan.py`. **A revalidação da §6 é
`Match.bank_unit()`** (D6), escrita pela feature 002 para exatamente isto e
documentada assim no próprio docstring. **A morte é uma varredura dos dois
bancos** (D8), porque `BankUnit` não sabe de quem é e porque o dano simultâneo
da §7.3 vai precisar da mesma forma.

Uma inconsistência da spec é resolvida no caminho, sem mudar cenário nenhum
(D9): "vida efetiva" aparece com dois sentidos — em FR-034 subtrai o dano, em
FR-044 não. As duas leituras são a mesma desigualdade escrita de dois jeitos, e
o plano dá nomes distintos às duas quantidades (`unit_max_health` e
`unit_remaining_health`) em vez de deixar o leitor adivinhar qual delas o nome
significa naquela linha.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova, e nenhum import novo de terceiros. Só o
que já existe: `apps.game.match` (feature 002) para o estado, a pilha, os
modificadores e a revalidação de alvo; `apps.game.cards` (feature 001) para
`CardCatalog`, `Spell`, `SpellEffect`, `TargetKind` e `EffectDuration`;
`apps.game.engine.player_action` e `round_cycle` (feature 005) para a forma da
ação e a cascata.

**Storage**: **muda, e é a primeira vez desde a feature 002.** `MatchPhase` ganha
`FINISHED`; `Match` ganha `outcome`; `MatchDocument` e `PlayerView` ganham a
chave `outcome`. Não há migration — a partida vive no Redis como JSON, e o
compare-and-swap de `store.py` não versiona esquema (o próprio `MatchDocument`
diz isso de si mesmo). Uma partida gravada antes desta feature não volta: não
existe partida em produção, e o campo novo é obrigatório no `TypedDict` por
decisão — um `total=False` deixaria o resto do documento igualmente opcional.

**Testing**: pytest 9.1, com `cd server && pytest`. Todos os testes desta feature
são síncronos e sem I/O — inclusive o de round-trip, que passa por
`to_match_document` / `match_from_document` direto, sem Redis.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`), uvicorn
com múltiplos workers. Importa aqui por um motivo: o estado terminal precisa ser
lido por qualquer worker, e é por isso que ele é campo do documento e não uma
exceção que um processo levantou e o outro nunca viu.

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`. Não
expõe HTTP nem websocket. Nada em `consumers/` muda nesta feature.

**Performance Goals**: o caminho quente continua sendo uma ação de jogador.
Lançar feitiço é uma busca linear numa mão de no máximo 10, um `catalog.card()`
(busca em `dict`), uma varredura de um banco de no máximo 6 e quatro mutações.
Resolver a pilha é uma passagem sobre ela, e cada entrada custa um
`match.bank_unit()` (no máximo 12 unidades) mais uma varredura de enterro (no
máximo 12). A pilha não tem teto declarado, mas é limitada pela energia e pela
mão: com energia máxima 10 e o feitiço mais barato custando 2, nenhuma rodada
empilha mais que 10 entradas.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`, sem relaxação nova em `mypy.ini`; funções de 4 a 20
linhas; arquivos abaixo de 500 linhas; nenhum campo `id` nu; nenhuma alteração
nos arquivos de teste das features 001, 002 e 005; nenhuma alteração na
varredura de modificadores do Fim de Rodada.

**Scale/Scope**: 7 módulos novos (6 em `engine/`, 1 em `match/`), 7 editados,
6 arquivos de teste novos e 1 auxiliar de teste novo. Nenhum arquivo de teste
existente é alterado.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | A §5B, a §6 e a §10 de `Game/Fluxo de Partida.md` são o contrato, e o exemplo canônico da §6 é um teste literal. Os valores dos cinco efeitos vêm do catálogo da feature 001, que os herdou do jogo anterior. As duas perguntas que a nota **não** responde — teto de Nexus, e Nexus a zero no meio da pilha — foram à sessão de esclarecimento e estão registradas na spec, não decididas em silêncio no código. Nenhuma nota nova é escrita. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | `target_card_instance_id` na ação e na entrada da pilha, `caster_user_id` no lançador, `defeated_user_ids` no resultado. Os dois campos novos do documento (`outcome.defeated_user_ids`) nomeiam o espaço. Nenhum `id` nu entra na serialização nem na visão do jogador. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | União fechada `SpellEffect` despachada por `match` exaustivo — um efeito novo sem braço é erro de mypy, que é a frase que `cards/effects.py` já escreveu prevendo esta feature. `MatchOutcome \| None`, `BankUnit \| None`, `CardInstanceId \| None` explícitos. Os dois estreitamentos de tipo (`Spell` na resolução, alvo obrigatório no aplicador) usam recusa nomeada, nunca `assert` — que some com `-O` — nem `cast`, que calaria o mypy sem responder. Nenhuma relaxação nova em `mypy.ini`. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | Sete módulos, um por responsabilidade, entre 40 e 200 linhas (D14). A função mais longa é o despacho de `apply_spell_effect`, com ~14 linhas de `match` e 1 nível de indentação. `resolve_stack` são 3 linhas de corpo mais três funções privadas de 3 a 6. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | Nenhum I/O novo, então nenhum fake de I/O novo. `FakeCardCatalog`, `ScriptedRandomSource`, `fake_match_state.py`, `fake_setup.py` e `match_snapshot.py` cobrem quase tudo; o único acréscimo é `fake_spell_board.py`, um construtor de tabuleiro no mesmo formato de `fake_match_state.py` — não é fake, não substitui I/O, e por isso é função e não classe. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova, nenhum bump, nenhum import de terceiros. |
| Estrutura Django previsível | ✅ PASS | Módulos dentro de pacotes que já existem. Sem app novo, sem `INSTALLED_APPS`, sem migration, sem URL, sem consumer. |
| Injeção de dependência | ✅ PASS | `catalog` chega por parâmetro nomeado em toda função que lê molde de carta. Nenhum módulo desta feature chama `mvp_catalog()` nem importa `random`. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy` e `black` rodam sem configuração nova. |
| Comentários preservados no refactor | ⚠️ ATENÇÃO | Cinco docstrings existentes deixam de ser previsão e viram fato; eles precisam ser **reescritos**, não apagados. Detalhe abaixo. |

### O que precisa ser reescrito, e por quê

Os cinco textos foram escritos prevendo esta feature. Nenhum está errado — todos
estão cumpridos, e o texto precisa passar do futuro para o presente.

1. **`engine/__init__.py`, docstring do pacote.** Hoje diz: *"A pilha da §6 e o
   combate da §7 caem no mesmo lugar quando entrarem."* A §6 entrou; a lista
   encolhe para o combate. O `__all__` cresce com a ação nova, as recusas novas,
   o aplicador de efeito, as consultas de vida e a §10 — e **não** cresce com
   `cast_spell` nem `resolve_stack`, pela razão que o próprio `__all__` já
   documenta para `run_upkeep` e `end_round`.

2. **`engine/round_cycle.py`, `_AUTOMATIC_PHASES`.** O comentário que explica a
   ausência de `STACK_RESOLUTION` — *"a feature que enche a pilha é a que precisa
   saber esvaziá-la"* — sai, porque a dívida que ele registrava está paga. O
   docstring de `_settle` e o de `_exit_action_phase` perdem o "não tem
   consumidor nesta feature" e ganham o que a Resolução de Pilha faz.

3. **`match/spell_stack.py`, docstring do módulo.** Hoje diz: *"Resolve em LIFO
   (§6). Quem resolve não é este módulo — aqui a entrada só é representada."*
   Continua verdade e **não muda**; vale registrar aqui porque é a razão de
   `StackEntry` não ganhar campo nenhum nesta feature.

4. **`cards/effects.py`, comentário da união.** Hoje diz: *"quando a pilha de
   feitiços for implementada, um `match` que esqueça um braço é erro de mypy."*
   A pilha foi implementada; o texto passa a apontar para
   `engine/spell_effect.py` como o `match` que ele previa.

5. **`match/match_state.py`, docstring de `MatchPhase`.** Hoje diz que `COMBAT`
   existe desde já mas o estado do combate entra depois. Ganha uma linha sobre
   `FINISHED`: terminal, sem transição de saída, e fora de `allowed_phases` de
   toda ação de propósito.

Quatro textos existentes passam a ser verificáveis por esta feature, e é bom que
não mudem:

- **`match/match_state.py`, `Match.bank_unit`**: *"É a revalidação de alvo da §6,
  e `None` não é erro: é a resposta que autoriza o fizzle."* Esta feature é o
  primeiro chamador, e D6 registra que nenhuma busca nova é escrita.
- **`match/spell_stack.py`, `StackEntry`**: *"`target_card_instance_id is None`
  significa que o feitiço não mira nada. Nunca significa que o alvo sumiu."*
  `CastSpellAction` herda a forma e a razão (D4).
- **`match/cards_in_play.py`, `BankUnit.damage_taken`**: *"Dano acumulado, não
  vida atual. Vida efetiva é o molde mais os modificadores de vida, menos isto —
  e fazer essa conta é do motor."* `unit_vitals.py` é o motor chegando ao lugar
  que aquele texto reservou.
- **`match/modifiers.py`, docstring do módulo**: *"Aplicar e varrer modificador
  não é deste pacote. Aqui eles só são representados."* Esta feature é a
  primeira a aplicar, e a varredura continua onde a feature 005 a pôs.

### Reverificação depois da Fase 1

O desenho fechado não mudou nenhum veredito. Seis pontos que a Fase 1 tornou
concretos:

- **Princípio I**: a inconsistência de "vida efetiva" entre FR-034 e FR-044 foi
  encontrada ao escrever `unit_vitals.py`, e não foi resolvida por escolha de
  implementação. As duas leituras são a mesma desigualdade, nenhum cenário de
  aceitação muda, e as duas quantidades ganharam nomes distintos (D9). A spec
  recebeu uma frase para deixar isso explícito.
- **Princípio II**: `MatchOutcome` ficou com `defeated_user_ids` e nenhum campo
  de vencedor. Gravar o vencedor seria a segunda fonte que
  `PlayerState.user_id` e `Match.awaiting_mulligan_user_ids` já recusam, cada um
  com a razão escrita no próprio docstring.
- **Princípio III**: a `__post_init__` de `MatchOutcome` valida a aridade — um ou
  dois `user_id`, sem repetição —, seguindo `FrozenCardCatalog`, que valida na
  construção justamente para não haver estado inválido a checar depois. Tupla
  vazia não é resultado de partida nenhuma.
- **Princípio IV**: o módulo maior depois da feature é `player_action.py`, que
  sobe de ~200 para ~290 linhas com o braço novo, `MatchIsOverError` e as duas
  guardas que sobem de `play_unit.py`. Longe do teto de 500, e a
  responsabilidade dele não mudou: continua sendo "a forma da entrada de jogador
  e o que ela precisa provar", que é o que o próprio docstring dele diz.
- **Princípio IV, de novo**: `unit_vitals.py` e `unit_damage.py` ficaram
  separados por consulta contra mutação (D14). Juntos passariam de 100 linhas
  com quatro responsabilidades misturadas, e as razões de mudar dos dois são
  diferentes — a conta de vida muda com palavras-chave, o efeito do dano muda
  com o combate.
- **Princípio V**: `test_cast_spell.py` prova a atomicidade das cinco recusas
  novas com `match_snapshot`, a foto do documento inteiro que a feature 005
  entregou. Nenhuma lista de campos escolhidos a dedo, e por isso os dois
  contadores da partida são conferidos sem que ninguém precise lembrar deles.

## Project Structure

### Documentation (this feature)

```text
specs/006-spell-stack-effects/
├── plan.md                       # Este arquivo
├── spec.md                       # A especificação
├── research.md                   # Fase 0 — 16 decisões de desenho e alternativas
├── data-model.md                 # Fase 1 — estado novo, transições, invariantes
├── quickstart.md                 # Fase 1 — como rodar e provar que funciona
├── contracts/
│   ├── cast_spell.md             # Fase 1 — a §5B, o braço novo e as 5 recusas
│   ├── stack_resolution.md       # Fase 1 — a §6 e as edições na cascata
│   └── spell_effect.md           # Fase 1 — o aplicador, vida, dano e a §10
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
        │   ├── match_outcome.py         # NOVO — MatchOutcome,
        │   │                            #   InvalidMatchOutcomeError
        │   ├── match_state.py           # EDITADO — MatchPhase.FINISHED,
        │   │                            #   Match.outcome, Match.is_over
        │   ├── documents.py             # EDITADO — MatchOutcomeDocument,
        │   │                            #   MatchDocument["outcome"]
        │   ├── serialization.py         # EDITADO — ida e volta do resultado
        │   ├── player_view.py           # EDITADO — PlayerView["outcome"]
        │   ├── __init__.py              # EDITADO — __all__
        │   ├── spell_stack.py           # NÃO TOCADO — StackEntry já basta
        │   ├── modifiers.py             # NÃO TOCADO — os três tipos já bastam
        │   └── cards_in_play.py         # NÃO TOCADO
        ├── engine/
        │   ├── cast_spell.py            # NOVO — §5B: cast_spell,
        │   │                            #   CardIsNotASpellError e as 4 recusas
        │   │                            #   de alvo
        │   ├── stack_resolution.py      # NOVO — §6: resolve_stack
        │   ├── spell_effect.py          # NOVO — apply_spell_effect, o despacho
        │   │                            #   exaustivo sobre os cinco
        │   ├── unit_vitals.py           # NOVO — unit_max_health,
        │   │                            #   unit_remaining_health, unit_is_dead,
        │   │                            #   unit_has_damage_immunity
        │   ├── unit_damage.py           # NOVO — deal_damage_to_unit,
        │   │                            #   bury_dead_units
        │   ├── victory.py               # NOVO — §10: change_nexus, check_victory
        │   ├── player_action.py         # EDITADO — CastSpellAction,
        │   │                            #   ActionKind.CAST_SPELL,
        │   │                            #   MatchIsOverError, card_in_hand,
        │   │                            #   ensure_enough_energy
        │   ├── round_cycle.py           # EDITADO — braço da ação nova,
        │   │                            #   STACK_RESOLUTION na cascata
        │   ├── play_unit.py             # EDITADO — usa as guardas que subiram
        │   ├── __init__.py              # EDITADO — __all__ e docstring
        │   ├── round_end.py             # NÃO TOCADO — é a prova de FR-062
        │   ├── upkeep.py                # NÃO TOCADO
        │   ├── card_draw.py             # NÃO TOCADO
        │   └── match_setup.py           # NÃO TOCADO
        ├── cards/
        │   └── effects.py               # EDITADO — só o comentário da união
        ├── consumers/                   # NÃO TOCADO — transporte está fora de escopo
        └── tests/
            ├── test_cast_spell.py               # NOVO — US1, US8
            ├── test_stack_resolution.py         # NOVO — US2, US3, US4
            ├── test_spell_effect.py             # NOVO — US5, US6
            ├── test_unit_damage.py              # NOVO — vida, dano, morte
            ├── test_victory.py                  # NOVO — US7
            ├── test_spell_state_round_trip.py   # NOVO — US9
            ├── fake_spell_board.py              # NOVO — tabuleiro com feitiços
            ├── match_snapshot.py                # reaproveitado, não alterado
            ├── fake_match_state.py              # reaproveitado, não alterado
            ├── fake_card_catalog.py             # reaproveitado, não alterado
            ├── test_spell_effects.py            # NÃO TOCADO — feature 001, a FORMA
            ├── test_match_serialization.py      # NÃO TOCADO
            ├── test_player_view.py              # NÃO TOCADO
            ├── test_round_end.py                # NÃO TOCADO — é a prova de FR-062
            ├── test_round_cycle.py              # NÃO TOCADO
            ├── test_play_unit.py                # NÃO TOCADO
            └── test_player_action.py            # NÃO TOCADO
```

**Structure Decision**: nenhum pacote novo. `engine/` continua plano, com um
módulo por regra, e a feature acrescenta seis. A razão de não juntá-los está em
[research.md](./research.md) D14: cada um tem uma razão própria para mudar, e o
grafo entre eles é um DAG raso.

```
round_cycle ──> cast_spell ──> player_action
     │              │
     │              └────────> (cards: Spell, TargetKind)
     │
     └────> stack_resolution ──> spell_effect ──> unit_damage ──> unit_vitals
                                      │
                                      └────────> victory ──> (match: MatchOutcome)
```

`victory.py` não importa `spell_effect.py`, e `unit_vitals.py` não importa nada
de `engine/`. Nenhum ciclo, e cada camada é testável sem a de cima.

`match/` **é** tocado, e isso é a diferença desta feature para as 004 e 005. Elas
não tocaram porque as regras delas só mexiam em campos que a feature 002 já
modelava; esta acrescenta o desfecho da partida, que não existia. O acréscimo é
mínimo e desenhado para não mexer em teste nenhum: uma chave no documento, uma
na visão do jogador, um valor de enum e um campo com default (D15).

`round_end.py` não é tocado, e isso é resultado, não sorte: os modificadores que
esta feature cria carregam a duração que o efeito declara, e a varredura da §8
já sabe o que fazer com ela. É o que faz FR-062 valer por construção.

`consumers/` também não é tocado. Quem chama `submit_action` com uma
`CastSpellAction` é a feature de transporte, e a spec a põe fora de escopo.

## Complexity Tracking

Nenhuma violação de princípio a justificar. Seis pontos que esta feature toca e
resolve ou registra:

| Ponto | O que é | Encaminhamento |
|---|---|---|
| Dois campos para um fato | `phase is FINISHED` e `outcome is not None` podem, em tese, discordar. | **Aceito com um escritor único** (D1). `_finish_match()` é a única função que escreve o par, e a invariante é afirmada por teste nos dois sentidos. As alternativas de um campo só perdem a cascata (sem fase) ou perdem quem ganhou (sem resultado). |
| A ordem das guardas da feature 005 | FR-061 congela "participante, prioridade, fase", e a partida terminada precisa de recusa própria. | **Resolvido sem mexer na ordem** (D3). `MatchIsOverError` é subclasse de `PhaseForbidsActionError`, levantada de dentro da terceira guarda. Consequência registrada: um `user_id` de fora numa partida terminada recebe `NotAParticipantError`, porque a guarda 1 é sobre identidade. |
| `unit_effective_attack` ausente | SACRIFICIAL FIRE escreve o modificador de ataque e nada nesta feature o lê. | **Deixado de fora de propósito** (D9). É a decisão oposta à D9 da feature 005, e a diferença é a mesma que aquela tabelou: lá a §5 mandava escrever a condição de saída e FR-016 a exigia; aqui nenhum FR pede, e o combate precisará da função junto das regras de bloqueio que só ele conhece. Os testes afirmam o modificador na unidade. |
| `apply_spell_effect` com um chamador só | O aplicador é exportado e a feature de combate ainda não existe. | **Exportado assim mesmo** (FR-064). O teste de US6 o exercita pelos dois caminhos — direto e via pilha — a partir do mesmo estado inicial, e é essa comparação que segura a promessa de que os dois caminhos dão o mesmo resultado. |
| A varredura de morte é mais larga que o necessário | `bury_dead_units` percorre os dois bancos; nenhum efeito desta feature mata quem não seja o alvo. | **Registrado, não estreitado** (D8). Descobrir o dono de um `BankUnit` exigiria varrer os jogadores de qualquer jeito, e o dano simultâneo da §7.3 vai matar várias unidades dos dois lados num evento só. Não muda nenhum resultado hoje. |
| `submit_action` depois de a partida terminar | Nesta feature só a resolução de pilha pode encerrar a partida, e ela acontece dentro de `_settle`, depois de `_pass_priority` e `_exit_action_phase`. | **Inalcançável hoje, registrado para o combate.** Nenhuma das três ações desta feature altera Nexus no momento em que é aplicada, então a ordem dos passos de `submit_action` nunca observa uma partida que acabou no meio deles. O feitiço imediato da §7.2 vai tornar isso alcançável, e é a feature de combate que precisa decidir onde a checagem entra. Não é escrito aqui porque nenhum FR o pede e nenhum teste poderia alcançá-lo. |
| Dois testes anteriores mudaram | `test_match_state.py::test_the_phase_set_is_closed` e `test_round_cycle.py::test_the_stack_branch_of_the_exit_is_wired`. | **Previsão da Fase 0 corrigida na implementação** (research D15). Os dois são inventários, não regras: um lista os valores de `MatchPhase`, o outro afirmava que a cascata parava numa fase sem corpo. Esta feature acrescenta a fase e dá corpo à outra, então os dois fatos mudaram — e os dois testes existem precisamente para forçar essa mudança a ser consciente. Nenhum teste de regra das features 001, 002 e 005 foi tocado, e SC-017 foi reescrito para dizer isso em vez de "nenhuma alteração". |
| A exaustividade do `match` não era verificada | Um `match` que devolve `None` não obriga o mypy a cobrir a união, ao contrário de `to_modifier_document`, que devolve valor. | **Encontrado ao implementar, corrigido com `assert_never`** no braço `case _` de `_dispatch`. Sem ele, FR-032 seria uma promessa sem mecanismo: um efeito novo sem braço passaria batido. Verificado removendo um braço e conferindo que o mypy reprova. |

**Registro no vault**: nada novo para `Backend/TODO.md`. O timeout de jogada
continua em aberto na §13 do Fluxo de Partida, é problema de transporte, e a
spec o põe fora de escopo por decisão — não por dívida desta feature.

**Uma correção na spec**: FR-044 recebe a precisão que D9 apurou, nomeando qual
das duas quantidades de vida a morte compara. Nenhum cenário de aceitação muda,
e nenhum requisito é acrescentado ou removido — a frase deixa de aceitar duas
leituras.
