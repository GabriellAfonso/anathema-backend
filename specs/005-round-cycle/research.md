# Research — Ciclo de Rodada

**Feature**: `005-round-cycle` | **Data**: 2026-09-10

Fase 0. Cada decisão registra o que foi escolhido, por quê, e o que foi
descartado. Nenhum NEEDS CLARIFICATION restou da spec — a única pergunta aberta
foi respondida na sessão de esclarecimento e está na seção Clarifications de
[spec.md](./spec.md).

As duas decisões que a spec mandou olhar com atenção são D1 (a forma da ação) e
D8 (a cascata). As outras existem para que essas duas fiquem como estão.

---

## D1 — A ação é uma união fechada de dataclasses, não um enum com saco de parâmetros

**Decisão**: `apps/game/engine/player_action.py` define

```python
PlayerAction = PlayUnitAction | PassAction
```

com cada braço `frozen=True, slots=True`, cada um carregando `actor_user_id` e
os parâmetros que aquele tipo exige, e cada um declarando dois `ClassVar`:
`action_kind` (o discriminante) e `allowed_phases` (as fases em que aquela ação
é legal).

**Rationale**: é o idioma que o projeto já usa três vezes para exatamente este
problema — `Card = Unit | Spell`, `UnitModifier = AttackModifier |
HealthModifier | DamageImmunity`, `SpellEffect`. Os dois primeiros documentam a
razão no próprio código: *"União fechada: um `match` sobre `Card` que esqueça um
braço é erro de mypy, não bug em produção."* Uma ação nova entra como um braço
novo, e todo despacho que a esquecer para de compilar.

O que isso ganha contra as alternativas, em ordem de importância:

1. **Os parâmetros pertencem à ação.** `PlayUnitAction` tem
   `card_instance_id`; `PassAction` não tem campo nenhum além do autor. Não
   existe `PassAction(card_instance_id=...)` a construir, e não existe
   `PlayUnitAction` sem carta. Com enum mais saco de parâmetros, os dois
   estados existem e alguém tem de checar em tempo de execução o que o tipo já
   podia ter proibido.
2. **A feature seguinte não muda o formato.** `CastSpellAction(actor_user_id,
   card_instance_id, target_card_instance_id)`,
   `DeclareAttackAction(actor_user_id, attacker_card_instance_ids)` e
   `AssignBlockerAction(...)` são braços novos. FR-046 pedido, FR-046 entregue.
3. **`allowed_phases` mantém a guarda 3 uniforme.** Ver D3.

**Alternativas descartadas**:

- *`ActionKind` (enum) mais um `dict` ou dataclass única com campos opcionais.*
  Deixa `card_instance_id: CardInstanceId | None` num passe, e o motor passa a
  validar em tempo de execução uma combinação que o tipo podia ter recusado.
  Também colide com o princípio III: campo anulável que nunca é `None` para
  metade dos casos é o mesmo argumento que `effects.py` usa contra um
  `requires_target` gravado.
- *Duas funções públicas independentes, `play_unit(match, user_id, card_id)` e
  `pass_priority(match, user_id)`, sem objeto de ação.* Funciona para esta
  feature e quebra na próxima: o transporte precisa de **uma** coisa para
  construir a partir do JSON e entregar ao motor, e sem ela cada ação nova
  acrescenta uma porta pública e um ramo no consumer. É também o oposto do que
  FR-046 pede.
- *`TypedDict` em vez de dataclass.* O envelope de websocket vai ser um
  `TypedDict` na feature de transporte, e é lá que ele deve morar. No motor a
  ação é um valor, e `frozen=True` diz que ninguém a altera no meio do caminho.

---

## D2 — A recusa é exceção, e `IllegalActionError` é a raiz das recusas novas

**Decisão**: uma jogada ilegal levanta. `IllegalActionError` é a base das
recusas que esta feature introduz; a guarda de participante reaproveita
`NotAParticipantError`, que já existe em `apps.game.match`.

**Rationale**: é a forma que o motor já usa para entrada de jogador inválida —
`MulliganAlreadyTakenError`, `CardNotInHandError`, `NotAParticipantError` — e é
o oposto do `None` da compra da §9, de propósito. A distinção que a feature 004
fixou: mão cheia é **fluxo normal** do jogo e por isso é valor de retorno;
jogada ilegal é entrada inválida e por isso levanta. Se a recusa virasse valor,
o caminho de sucesso de `submit_action` teria de devolver duas coisas — o
estado e o "deu certo?" — e todo chamador teria de lembrar de olhar a segunda.

FR-052 pede que o cliente distinga os casos sem interpretar texto livre: cada
guarda tem sua própria classe, e cada classe carrega os valores ofensores como
atributos, não só dentro da mensagem.

**Alternativas descartadas**:

- *Um `ActionRefused` como valor de retorno.* Ver acima. Também deixaria o
  chamador seguir por engano com a partida intacta achando que jogou.
- *Uma exceção só, com um campo `reason: str`.* Recusa genérica com etiqueta,
  que é o que FR-051 proíbe. E `match` sobre string não é conferido por
  ninguém.
- *Fazer `NotAParticipantError` herdar de `IllegalActionError`.* Inverteria a
  dependência: `apps.game.match` passaria a importar de `apps.game.engine`, e o
  pacote de estado diz de si mesmo que não conhece regra. A raiz dupla é o
  preço, e ele é pequeno: quem quiser pegar tudo pega
  `(NotAParticipantError, IllegalActionError)`.

---

## D3 — `allowed_phases` mora na ação, não numa cadeia de `if` na guarda

**Decisão**: cada braço declara `allowed_phases: ClassVar[frozenset[MatchPhase]]`.
Nesta feature os dois declaram `frozenset({MatchPhase.ACTION})`.

**Rationale**: FR-044 escreve a guarda 3 como *"a fase atual permite **esta**
ação"* — a pergunta é sobre a ação, não sobre a partida. Com o conjunto na
ação, a guarda comum lê só campos da ação e não precisa saber qual ação é:

```python
if match.phase not in action.allowed_phases:
    raise PhaseForbidsActionError(...)
```

Sem ele, a guarda "comum" precisaria abrir um `match` sobre o tipo da ação para
descobrir a fase permitida — e aí ela deixa de ser comum, que é justamente o que
FR-044 e FR-046 pedem que ela seja. O bloqueio da §7.2 acontece em `COMBAT`, não
em `ACTION`; quando ele entrar, é um `frozenset` diferente num braço novo, e a
guarda não muda.

O mesmo argumento de `ClassVar` que `modifiers.py` já usa: a fase permitida
pertence à mecânica, não à instância, então nenhum call site consegue construir
um passe que se diz legal no Upkeep.

**Alternativas descartadas**:

- *`if match.phase is not MatchPhase.ACTION` na guarda comum, com comentário.*
  Menos código hoje. Mas transforma a guarda comum em guarda de uma fase só, e a
  feature de combate reescreve a função em vez de acrescentar um braço.
- *Um `dict[ActionKind, frozenset[MatchPhase]]` no módulo.* Segunda fonte de
  verdade a manter em sincronia com a união, e o mypy não cobra a entrada
  faltante.

---

## D4 — `CardNotInHandError` sai de `mulligan.py` e vira recusa compartilhada

**Decisão**: a exceção migra para `player_action.py`. `mulligan.py` passa a
importá-la de lá. `engine/__init__.py` continua reexportando o mesmo nome.

**Rationale**: a pergunta é idêntica nos dois lugares — *"a carta citada está na
mão daquele jogador?"* — e a mensagem já é a certa para os dois: cita o
identificador pedido, o `user_id` e a mão. Reescrevê-la em `play_unit.py` seria
duplicação de lógica, que o princípio IV proíbe. Deixá-la em `mulligan.py` e
importar de lá poria a §5A dependendo do módulo do setup, que é a direção
errada: a §5A não tem nada a ver com o mulligan.

O que isso custa: `mulligan.py` passa a importar de `player_action.py` mesmo não
sendo o mulligan uma `PlayerAction` nesta feature. O módulo é *"a forma da
entrada de jogador e o que ela precisa provar"*, e a exceção cabe nessa
descrição. Quando o mulligan virar uma ação — a spec já registra que a forma vai
ser reusada por ele —, o import deixa de ser assimétrico.

Nenhum teste muda: `test_mulligan.py` importa de `apps.game.engine`, não do
módulo.

**Alternativas descartadas**:

- *Uma segunda exceção com nome parecido em `play_unit.py`.* Dois nomes para uma
  pergunta, e o cliente teria de tratar os dois.
- *Módulo próprio só para a exceção.* Um arquivo de dez linhas para uma classe
  que já tem um lugar coerente.

---

## D5 — Cinco módulos novos no `engine/`, um por seção do Fluxo de Partida

**Decisão**:

| Módulo | Responsabilidade | Seção |
|---|---|---|
| `player_action.py` | A forma da ação e as guardas comuns | §5 (alternância) |
| `play_unit.py` | A regra de jogar unidade | §5A |
| `upkeep.py` | A recarga e a compra de início de rodada | §4 |
| `round_end.py` | A varredura, a troca de token e a virada de rodada | §8 |
| `round_cycle.py` | As duas portas públicas e a cascata | §4→§5→§8→§4 |

**Rationale**: cada arquivo tem uma razão para mudar, e o grafo de dependência é
um DAG raso: `round_cycle` → {`upkeep`, `round_end`, `play_unit`,
`player_action`}, e `play_unit` → `player_action`. Nenhum ciclo, e nenhum
módulo precisa conhecer a cascata para ser testado.

O tamanho estimado de cada um fica entre 40 e 120 linhas — a mesma faixa dos oito
módulos de `match/` e dos quatro de `engine/`. Juntar tudo num `round_cycle.py`
daria um arquivo na casa de 350 linhas com cinco responsabilidades, ainda abaixo
do teto de 500 e ainda assim errado pelo princípio IV.

**Alternativas descartadas**:

- *Um módulo só, `round_cycle.py`.* Ver acima.
- *Um pacote `engine/round/`.* Aninhamento sem ganho: `engine/` é plano hoje,
  com um módulo por regra, e a feature não muda essa forma.
- *Pôr o Upkeep dentro de `card_draw.py`, já que ele compra.* Inverteria a
  dependência — a compra é a regra geral da §9 e não pode conhecer quem a chama.

---

## D6 — As portas públicas são duas, e as duas mutam a partida no lugar

**Decisão**:

```python
def begin_round_cycle(match: Match, *, randomness: RandomSource) -> None: ...
def submit_action(
    match: Match, action: PlayerAction, *, catalog: CardCatalog,
    randomness: RandomSource,
) -> None: ...
```

As duas alteram `match` e devolvem `None`.

**Rationale**: é a forma de `record_mulligan` e de `finish_setup`, e o chamador
já sabe lidar com ela — o `MatchStore.mutate` da feature 003 recebe uma função
que altera a partida no lugar. Devolver um `Match` novo obrigaria ou a copiar o
estado inteiro (e aí a identidade de objeto do `BankUnit` que acabou de entrar
no banco deixa de ser a mesma) ou a devolver o mesmo objeto sob outro nome, que
é pior: sugere imutabilidade que não existe.

FR-039 pede o estado estabilizado como resultado, e ele é: quando `submit_action`
retorna, `match` já está na Fase de Ação da rodada certa. A spec fala em
"devolve o estado novo" no sentido de "o que o chamador lê depois", não de valor
de retorno.

A atomicidade da recusa (FR-048) não sofre com isso porque nenhuma regra muta
antes de todas as suas guardas passarem — ver D7.

**Alternativas descartadas**:

- *Devolver um `Match` novo, imutável.* Reescreveria `match/` inteiro, que é
  `dataclass(slots=True)` mutável por decisão da feature 002.
- *Devolver o `PlayerView` do autor.* Mistura camadas: a view é do transporte, e
  a spec põe o envelope fora de escopo.

---

## D7 — Valida tudo, muta depois: a atomicidade vem da ordem, não de rollback

**Decisão**: toda regra desta feature separa fisicamente as duas metades. Em
`play_unit`, as quatro perguntas — carta na mão, carta é unidade, energia
suficiente, banco com espaço — acontecem antes da primeira atribuição.

**Rationale**: FR-048 pede que a recusa deixe o estado idêntico *em qualquer
ponto de falha*. Há duas formas de conseguir isso: desfazer o que foi feito, ou
não fazer nada até ter certeza. A segunda é a que `record_mulligan` já usa —
*"Valida tudo antes de mutar qualquer coisa"* — e é a única que não tem estado
intermediário a esquecer. Um rollback precisa lembrar de cada campo tocado, e o
campo que alguém esquecer não dá erro: dá partida em estado que nenhuma regra
produziria, que é o que a spec chama de pior que ação nenhuma.

A consequência prática é que a ordem das checagens específicas é parte da
regra e está fixada na spec: carta na mão → carta é unidade → energia → banco. A
carta precisa ser resolvida antes que se possa citar o custo dela na recusa de
energia.

**Alternativas descartadas**:

- *Copiar a partida, aplicar, e descartar a cópia em caso de erro.* Custo de
  cópia por ação e uma segunda árvore de objetos viva no meio da jogada. E
  esconderia um erro de ordem em vez de impedi-lo.
- *Um gerenciador de contexto de transação.* Máquina para um problema que a
  ordem resolve de graça.

---

## D8 — A cascata é um laço sobre fases automáticas, não uma sequência fixa

**Decisão**: depois da ação e da troca de prioridade, `submit_action` chama um
passo de assentamento:

```python
_exit_action_phase(match)          # a saída da §5
_settle(match, randomness)         # atravessa toda fase automática
```

onde `_settle` é

```python
while match.phase is MatchPhase.ROUND_END or match.phase is MatchPhase.UPKEEP:
    _run_automatic_phase(match, randomness)
```

`end_round` termina pondo a partida em `UPKEEP`; `run_upkeep` termina pondo-a em
`ACTION`. O laço roda no máximo duas voltas e termina sempre — não existe fase
automática que leve a outra fase automática que leve de volta à primeira.

**Rationale**: é a diferença que a spec marcou como decisiva. Uma implementação
que execute um passo por chamada satisfaz cada regra isolada, passa em todo
teste unitário de fase, e trava na primeira partida real com a partida parada em
`ROUND_END` esperando um empurrão que ninguém dá.

O laço, e não uma chamada encadeada (`end_round(); run_upkeep()`), por dois
motivos:

1. **A saída da §5 não sabe qual fase vem.** Ela decide entre `ROUND_END` e
   `STACK_RESOLUTION`. Quem atravessa é o laço, que lê a fase que estiver lá.
2. **A feature de pilha encaixa sem reescrever.** Ela acrescenta
   `STACK_RESOLUTION` à condição do laço e o corpo correspondente ao despacho.
   A saída da §5, escrita agora, não muda.

FR-040 e FR-041 são consequência: quando `submit_action` retorna, a fase é
`ACTION`, e nenhum estado intermediário é observável porque nenhum deles
atravessa a fronteira da função.

**Alternativas descartadas**:

- *`end_round()` chamar `run_upkeep()` no fim, e `run_upkeep()` não chamar
  ninguém.* Encadeamento por dentro das regras. Cada fase passa a conhecer a
  seguinte, e a §8 vira dona da §4. Também torna impossível testar o Fim de
  Rodada isolado sem executar um Upkeep junto.
- *Um passo por chamada, com o chamador em laço.* Empurra a cascata para o
  transporte, que é onde ela mais falha em silêncio.
- *Recursão em vez de laço.* Mesma coisa com mais pilha e sem ganho de leitura.

---

## D9 — O ramo `STACK_RESOLUTION` é escrito e fica sem quem o consuma

**Decisão**: `_exit_action_phase` escreve as duas condições da §5, incluindo a
que leva à Resolução de Pilha. `_settle` **não** conhece `STACK_RESOLUTION`.

**Rationale**: FR-016 pede a condição escrita, e a razão está na spec: a feature
de pilha encaixa nela sem reescrever a saída. Quem não pode ser escrito agora é
o corpo da resolução — ele é a §6 inteira, e está fora de escopo.

Isso é uma tensão com o que a feature 004 decidiu ao apagar `EmptyDeckError` por
ser um braço inalcançável, e vale registrar a diferença:

| | `EmptyDeckError` (004) | `STACK_RESOLUTION` (005) |
|---|---|---|
| Por que era inalcançável | Pela própria regra, para sempre — a §9 prova que o caminho não existe | Porque nenhuma feature enche a pilha **ainda** |
| O que a nota de decisão diz | Nada a exigia | A §5 escreve a condição, literalmente |
| O que acontece quando a feature seguinte chegar | Nada, ela continuaria inalcançável | Ela passa a ser o caminho normal |

O braço é, portanto, uma costura documentada e não código morto. Duas coisas o
mantêm honesto:

- um teste que põe um feitiço na pilha à mão, faz os dois passarem, e afirma que
  a partida chega a `STACK_RESOLUTION` e para ali — o encaixe que a feature de
  pilha vai consumir;
- um teste que roda dez rodadas completas e afirma que a pilha continua vazia o
  tempo todo, para que o dia em que alguém empilhar sem ligar a resolução não
  passe despercebido.

**Alternativas descartadas**:

- *Não escrever a condição, e a feature de pilha reescrever a saída.* É o que
  FR-016 proíbe, e a razão é boa: a saída da §5 é o ponto em que um erro de
  ordem não dá erro, dá partida travada.
- *Escrever a condição e levantar ao alcançá-la.* Transformaria um estado
  previsto pela nota de decisão em erro, e a feature de pilha teria de apagar a
  exceção antes de usar o caminho.

---

## D10 — A ordem do Upkeep é a ordem do par, e é fixada em teste

**Decisão**: `run_upkeep` itera `match.players` na ordem em que eles estão, e
essa ordem é a garantia. O contador de sorteios continua sendo um só, da
partida.

**Rationale**: é a resposta da sessão de esclarecimento, e a razão longa está na
seção Clarifications de [spec.md](./spec.md). O que o código precisa carregar é
a distinção: a §4 garante **independência** — nenhum passo do Upkeep de um
jogador lê o estado do outro — e não indiferença à ordem. A ordem existe, é
sempre a mesma, e é o que torna reproduzível um Upkeep em que os dois jogadores
resetam o deck.

Duas coisas seguram isso:

- iterar `match.players` e nada mais. Ordenar por `user_id`, por prioridade ou
  por dono do token amarraria a sequência de sorteios a um campo que muda de
  rodada para rodada;
- um teste com os dois decks vazios e os dois cemitérios cheios, rodando duas
  vezes a partir do mesmo estado, comparando as duas partidas resultantes.

**Alternativas descartadas** (as duas da pergunta de esclarecimento):

- *Um contador de sorteios por jogador.* Muda o estado e a serialização da
  feature 002, e obriga a revisitar o round-trip e o setup por um problema que
  a ordem fixa resolve.
- *Ordinal derivado de `(rodada, user_id)`.* Muda a regra de cunhagem de sorteio
  da partida inteira — setup, mulligan e reset de deck juntos.

---

## D11 — `MAX_BANK_SIZE` mora com a regra que o aplica

**Decisão**: `MAX_BANK_SIZE = 6` em `play_unit.py`; `MAX_ENERGY = 10` e
`ENERGY_PER_ROUND = 1` em `upkeep.py`.

**Rationale**: é o que o projeto já faz — `MAX_HAND_SIZE` mora em
`card_draw.py`, `DECK_SIZE` em `deck_rules.py`, `STARTING_NEXUS` em
`player_state.py` — e é o que o docstring de `PlayerState` manda, ao dizer que
*"os tetos de mão (10) e de banco (6) da §12 **não** são validados aqui.
Aplicá-los é regra — o de mão acontece na compra (§9), o de banco ao jogar
unidade (§5A)"*. Esta feature é a §5A chegando ao lugar que aquele texto
reservou.

**Alternativas descartadas**:

- *Um `constants.py` com a §12 inteira.* O projeto não tem, e um módulo de
  constantes separa o valor da regra que o justifica — quem lê a constante
  perde a razão, e quem lê a regra perde o valor.
- *As constantes no `match/`.* Aplicá-las é regra, e o pacote de estado diz de
  si mesmo que não faz regra.

---

## D12 — A troca de token lida com `token_holder_user_id` anulável na hora

**Decisão**: `round_end._swap_token` lê o campo, recusa o `None` citando o
`match_id`, e só então chama `Match.opponent_of`.

**Rationale**: `token_holder_user_id` é `int | None` porque no meio do setup não
existe dono de token — decisão da feature 002, e boa. Sob `mypy strict` o `None`
precisa ser estreitado em algum lugar, e o lugar honesto é aqui: o Fim de Rodada
só é alcançável a partir da Fase de Ação, que só existe depois do sorteio, então
o `None` é estado corrompido. Reaproveita `NotAParticipantError`, que aceita
`int | None` de propósito e cita o valor ofensor.

**Alternativas descartadas**:

- *`assert match.token_holder_user_id is not None`.* Some com `-O`, e o projeto
  não usa esse estilo.
- *`cast(int, ...)`.* Silencia o mypy sem responder a pergunta, e é o tipo de
  buraco que o princípio III proíbe.
- *Tornar o campo não-anulável com um valor de espera.* É o que a feature 002
  descartou por escrito: *"não é valor de espera: no meio do setup não existe
  dono do token, e afirmar um seria mentir num campo que ninguém checa"*.

---

## D13 — O catálogo chega por parâmetro a `submit_action`, e o Upkeep não precisa dele

**Decisão**: `submit_action(match, action, *, catalog, randomness)`.
`begin_round_cycle(match, *, randomness)` e `run_upkeep(match, *, randomness)`
não recebem catálogo.

**Rationale**: só a §5A precisa do molde da carta — o custo e o tipo vivem no
catálogo, e a `MatchCard` guarda apenas `card_instance_id` e `card_id`, por
decisão da feature 002. É a mesma injeção que `start_match(catalog=...)` já
usa. `PassAction` não precisa do catálogo, mas `submit_action` é uma porta só e
recebe o que a mais cara das ações exige — separar as portas para poupar um
parâmetro desfaria D1.

**Alternativas descartadas**:

- *Guardar o catálogo dentro do `Match`.* O catálogo é global e imutável, a
  partida é por sessão e vai ao Redis; guardá-lo dentro obrigaria a serializá-lo
  ou a reconstruí-lo na leitura.
- *Importar `mvp_catalog()` dentro do módulo.* Dependência alcançada por import,
  que a constituição proíbe.

---

## D14 — Testes: seis arquivos novos e um auxiliar de fotografia de estado

**Decisão**:

| Arquivo | O que prova |
|---|---|
| `test_upkeep.py` | US2 — progressão de energia, teto, compra, mão cheia, ordem fixa, independência |
| `test_play_unit.py` | US3 — a jogada aceita, e as quatro recusas específicas |
| `test_action_phase.py` | US4 — passar, a troca de prioridade, a saída da fase |
| `test_round_end.py` | US5 — varredura, dano intacto, token, rodada |
| `test_round_cycle.py` | US1, US6, US8 — o primeiro empurrão, a cascata, dez rodadas, round-trip |
| `test_player_action.py` | US7 — as três guardas comuns, a ordem entre elas, a atomicidade |

Mais um auxiliar, `tests/match_snapshot.py`, com uma função só:

```python
def match_snapshot(match: Match) -> MatchDocument: ...
```

**Rationale**: FR-048 e SC-007 pedem "idêntico campo a campo" para cada uma das
recusas. Escrever essa comparação à mão em cada teste seria a mesma duzia de
linhas repetida oito vezes, e cada cópia poderia esquecer um campo — inclusive
os dois contadores, que são exatamente o que FR-050 quer conferir.
`to_match_document` já converte a partida inteira, é comparável por `==`, e é o
mesmo caminho que a feature 002 usa para provar o round-trip. Uma foto antes,
uma depois, uma comparação.

Não é um fake: não substitui I/O nenhum, e por isso não é uma classe. É um
auxiliar de teste, e mora entre os testes.

**Alternativas descartadas**:

- *`copy.deepcopy(match)` e comparar os objetos.* `Match` é `slots=True` sem
  `eq` gerado em toda a árvore, e a comparação sairia por identidade em alguns
  níveis — passaria sem provar nada.
- *Conferir campo a campo à mão em cada teste.* Ver acima.

Os fakes existentes cobrem o resto: `fake_match_state.py` para estados montados
à mão (é dele que sai o modificador temporário posto à mão da US5),
`fake_setup.py` para a partida que saiu do motor de verdade,
`fake_card_catalog.py` para os moldes com valores redondos,
`fake_random_source.py` para a ordem ditada e o determinismo. Um acréscimo:
`fake_setup.fake_match_in_action_phase()`, que é `fake_match_ready_for_upkeep()`
mais `begin_round_cycle`.
