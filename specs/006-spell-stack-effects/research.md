# Research — Pilha de Feitiços e Efeitos

**Feature**: `006-spell-stack-effects` | **Data**: 2026-09-10

Fase 0. Cada decisão registra o que foi escolhido, por quê, e o que foi
descartado. Nenhum NEEDS CLARIFICATION restou da spec — as duas perguntas
abertas foram respondidas na sessão de esclarecimento e estão na seção
Clarifications de [spec.md](./spec.md).

As decisões que carregam a feature são D1 (o estado terminal), D7 (o aplicador
que não sabe de onde veio) e D11 (a pilha que para). As outras existem para que
essas três fiquem como estão.

Uma inconsistência da própria spec é resolvida aqui, em D9: "vida efetiva"
aparece com dois sentidos diferentes em FR-034 e FR-044. Nenhum cenário de
aceitação muda; o que muda é que as duas quantidades passam a ter nomes
distintos.

---

## D1 — O fim da partida é um par de campos escritos por um ponto só

**Decisão**: `apps.game.match` ganha dois campos e um valor de fase.

```python
class MatchPhase(StrEnum):
    ...
    FINISHED = "finished"

@dataclass(slots=True)
class Match:
    ...
    outcome: MatchOutcome | None = None

    @property
    def is_over(self) -> bool:
        return self.outcome is not None
```

`outcome is None` é partida em andamento. `outcome is not None` implica
`phase is FINISHED`, e a implicação vale nos dois sentidos. **Um único ponto do
código escreve o par** — `_finish_match()` em `engine/victory.py` —, e é a
existência desse ponto único que torna a invariante afirmável em vez de
esperançosa.

**Rationale**: a §10 descreve o fim da partida como estado, não como evento nem
como exceção. FR-051 pede que ele seja reconhecível no próprio estado, FR-065
que sobreviva ao Redis, e a feature 002 diz de si mesma que o estado é lido por
qualquer worker do uvicorn. Nada disso é atendido por um `raise`.

Os dois campos existem porque respondem perguntas diferentes, e as duas
perguntas têm consumidores diferentes:

- **`phase`** é o que a cascata de `round_cycle` lê para decidir se continua, e
  o que `allowed_phases` compara para decidir se uma ação é legal. `FINISHED`
  não está em `_AUTOMATIC_PHASES` nem em nenhum `allowed_phases`, então a
  partida terminada para a cascata e recusa toda ação **sem uma linha nova em
  nenhum dos dois lugares** (D10, D3).
- **`outcome`** é quem perdeu. `phase` não sabe dizer isso e não deveria: um
  `MatchPhase` com três valores terminais — `PLAYER_ONE_LOST`,
  `PLAYER_TWO_LOST`, `DRAW` — misturaria a fase do ciclo de rodada com o
  resultado da partida, e faria toda comparação de fase existente ter de saber
  de três valores em vez de um.

**Alternativas descartadas**:

- *Só `outcome`, sem fase terminal.* A cascata giraria para sempre: a resolução
  de pilha que termina a partida deixaria `phase` em `STACK_RESOLUTION`, que é
  fase automática, e `_settle` a atravessaria de novo com a pilha já vazia. Daria
  para consertar com um `if match.is_over` em cada fase automática — três
  lugares a lembrar em vez de um valor que já é lido.
- *Só a fase terminal, sem `outcome`.* Perde quem perdeu, que é o que FR-051
  pede. Recuperá-la depois lendo os Nexus não funciona: o §10 fala de "no mesmo
  cálculo", e um jogador com Nexus 0 depois de um empate não é distinguível de
  um jogador com Nexus 0 numa derrota simples sem o registro.
- *`winner_user_id: int | None` mais `is_draw: bool`.* Dois campos que podem
  discordar — `winner_user_id=7, is_draw=True` é estado que não é estado nenhum.
  É o mesmo argumento que `effects.py` usa contra um `requires_target` gravado.
- *Levantar uma exceção `MatchOverError` de dentro do efeito.* Terminaria a
  resolução no meio sem gravar nada, e o chamador teria de reconstruir o estado
  final a partir do que pegou. A partida acabar não é erro; é o desfecho normal.

---

## D2 — `MatchOutcome` nomeia os derrotados, e o empate é derivado

**Decisão**: `apps/game/match/match_outcome.py`

```python
@dataclass(frozen=True, slots=True)
class MatchOutcome:
    defeated_user_ids: tuple[int, ...]

    @property
    def is_draw(self) -> bool:
        return len(self.defeated_user_ids) == 2
```

com validação na construção: um ou dois `user_id`, sem repetição. Zero e três
levantam `InvalidMatchOutcomeError` citando o valor recebido.

**Rationale**: a §10 tem um fato primitivo só — *quem chegou a Nexus ≤ 0*. Vitória
e empate são leituras dele: um derrotado é derrota do outro, dois é empate.
Gravar o fato primitivo e derivar as leituras é o que o projeto já faz com
`PlayerState.user_id` (derivado de `profile`),
`Match.awaiting_mulligan_user_ids` (derivado de `mulligan_taken`) e
`SpellEffectShape.requires_target` (derivado de `target_kind`) — e os três
docstrings dizem a mesma razão: uma segunda fonte não dá erro quando diverge, dá
estado errado que passa despercebido.

A validação na construção segue `FrozenCardCatalog.__init__`, que valida alto e
cedo justamente para não haver estado inválido a checar depois. Tupla vazia e
tupla de três não são resultados de partida — são bug de quem construiu.

**Não existe campo de vencedor.** Quem quer o vencedor tem os dois jogadores em
`match.players` e a lista de derrotados; derivar é uma linha. Gravar seria a
segunda fonte que este mesmo argumento recusa.

**Alternativas descartadas**:

- *`loser_user_id: int | None` mais `is_draw: bool`.* Mesmo problema de D1: os
  dois campos podem discordar.
- *`MatchOutcome` como `StrEnum` de três valores.* Perde qual dos dois jogadores
  perdeu — `PLAYER_ONE_LOST` só faz sentido para quem sabe a ordem do par, e a
  ordem do par é detalhe da serialização, não identidade (princípio II).
- *`frozenset[int]` em vez de tupla.* Não sobrevive ao JSON sem conversão, e a
  ordem estável da tupla torna o documento comparável por `==` — que é como
  `match_snapshot` prova atomicidade.

---

## D3 — A recusa de partida terminada é subclasse da recusa de fase

**Decisão**: `MatchIsOverError(PhaseForbidsActionError)`, levantada de dentro da
**terceira** guarda de `ensure_action_allowed`, quando a fase é `FINISHED`. A
ordem das guardas da feature 005 — participante, prioridade, fase — não muda.

```python
if match.phase is MatchPhase.FINISHED:
    raise MatchIsOverError(action.action_kind, match.outcome, match.match_id)

if match.phase not in action.allowed_phases:
    raise PhaseForbidsActionError(...)
```

**Rationale**: três requisitos que puxam em direções diferentes, e esta forma
atende os três:

1. **FR-061** — a ordem das guardas comuns da feature 005 não muda. Uma guarda
   nova *antes* da de participante mudaria a sequência documentada, e o
   contrato da 005 escreve essa ordem como parte do contrato ("um autor que
   falha em duas guardas recebe a recusa da primeira delas, sempre").
2. **FR-052** — a recusa cita que a partida acabou. `PhaseForbidsActionError`
   genérico diria "ação 'cast_spell' não é permitida na fase 'finished'", que é
   verdade e é uma resposta ruim: não diz quem ganhou, e trata o fim da partida
   como se fosse o Upkeep.
3. **FR-060** — a guarda que falhou é distinguível sem interpretar texto. Classe
   própria resolve.

Subclasse e não classe irmã porque quem hoje escreve `except
PhaseForbidsActionError` continua pegando o caso, e porque a afirmação é
literalmente verdadeira: a fase proíbe a ação. É a mesma relação de
`NotYourPriorityError` com `IllegalActionError`.

Consequência aceita e registrada: **um `user_id` de fora agindo numa partida
terminada recebe `NotAParticipantError`, não `MatchIsOverError`.** A guarda 1 é
sobre identidade e vem antes; quem não joga a partida não tem direito nem à
notícia de que ela acabou.

**Alternativas descartadas**:

- *Guarda 0, antes de participante.* Melhor mensagem para o espectador, ao custo
  de mudar a ordem que FR-061 congela. O ganho não paga.
- *Nenhuma exceção nova, deixar `PhaseForbidsActionError` genérico cobrir.*
  Gratuito, e falha FR-052.
- *Cada ação declarar `FINISHED` fora de `allowed_phases` e nada mais.* É o que
  já acontece por construção; a exceção específica é o que se acrescenta a isso,
  não uma substituição.

---

## D4 — `CastSpellAction` é um braço novo, e o alvo é um `CardInstanceId | None`

**Decisão**:

```python
@dataclass(frozen=True, slots=True)
class CastSpellAction:
    action_kind: ClassVar[ActionKind] = ActionKind.CAST_SPELL
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})

    actor_user_id: int
    card_instance_id: CardInstanceId
    target_card_instance_id: CardInstanceId | None = None

PlayerAction = PlayUnitAction | PassAction | CastSpellAction
```

**Rationale**: é exatamente o encaixe que a feature 005 escreveu prevendo esta.
O plano da 005 nomeia `CastSpellAction(actor_user_id, card_instance_id,
target_card_instance_id)` como exemplo de que o formato comporta a ação
seguinte, e `ensure_action_allowed` não muda uma linha para recebê-la. FR-046 da
005 pedido, FR-001 desta entregue.

`target_card_instance_id` é anulável e o default é `None` porque a ausência de
alvo é **estado legítimo** de três dos cinco feitiços — não é um campo que às
vezes esqueceram de preencher. É a mesma forma e a mesma razão de
`StackEntry.target_card_instance_id`, cujo docstring já separa as duas
perguntas: *"`None` significa que o feitiço não mira nada. Nunca significa que o
alvo sumiu."*

`CardInstanceId` e não `CardId`: a jogada mira **aquela** cópia no banco, e o
`NewType` da feature 002 faz trocar um pelo outro ser erro de mypy.

**Alternativas descartadas**:

- *Dois braços, `CastTargetedSpellAction` e `CastUntargetedSpellAction`.*
  Duplicaria as três primeiras guardas específicas (carta na mão, é feitiço,
  energia) e transferiria para o cliente a decisão de qual construir — decisão
  que depende do catálogo, que é do servidor. O motor recusaria de qualquer
  jeito, mas com a recusa errada.
- *Alvo como `BankUnit`.* A nota de implementação da §6 proíbe explicitamente:
  *"A pilha guarda IDs de alvo, nunca referência direta a objeto."* Vale para a
  ação pelo mesmo motivo — ela atravessa o websocket antes de chegar ao motor.

---

## D5 — Quatro recusas de alvo, uma por pergunta

**Decisão**: `cast_spell.py` levanta quatro recusas distintas, todas
`IllegalActionError`:

| Recusa | Quando | Cita |
|---|---|---|
| `SpellTakesNoTargetError` | efeito com `target_kind is NONE` e a ação mandou alvo | a carta e o alvo recebido |
| `SpellNeedsTargetError` | efeito exige alvo e a ação não mandou | a carta e o `TargetKind` esperado |
| `WrongSpellTargetSideError` | o alvo está em campo, no banco errado | o alvo, o `TargetKind` esperado, e de quem é o banco |
| `SpellTargetNotOnBattlefieldError` | o alvo não está em banco nenhum | o alvo |

Mais `CardIsNotASpellError`, simétrica à `CardIsNotAUnitError` que a feature 005
já entregou.

**Rationale**: FR-060 pede que o cliente distinga os casos sem interpretar texto
livre, e a spec lista os quatro como casos separados nos Edge Cases. Uma classe
por pergunta é como o pacote já responde isso — sete recusas distintas entre
`player_action.py` e `play_unit.py`, cada uma com o valor ofensor em atributo
nomeado.

A distinção que mais importa é a última linha contra a penúltima: **alvo no
banco errado** e **alvo que não existe** são erros de cliente diferentes. O
primeiro é uma tela que ofereceu um alvo que a carta não aceita; o segundo é
uma tela desatualizada. Colapsar os dois numa recusa só esconde qual dos dois
está quebrado.

E `SpellTargetNotOnBattlefieldError` é a que a spec separa de fizzle com
insistência: **recusa é o alvo não existir no lançamento; fizzle é ele sumir
entre o lançamento e a resolução.** São o mesmo fato em momentos diferentes, com
respostas opostas — uma rejeita a jogada, a outra a consome. Duas classes
diferentes de resposta (exceção contra nada) já garantem isso, mas o nome longo
existe para que ninguém as confunda ao ler.

**Alternativa descartada**: *uma `InvalidSpellTargetError` com um campo `reason:
StrEnum`.* Move a distinção de tipo para valor, e um `match` sobre o `reason`
deixa de ser exaustivo para o mypy — perde exatamente a propriedade que a união
fechada existe para dar.

---

## D6 — A revalidação da §6 é `Match.bank_unit()`, que a feature 002 já escreveu

**Decisão**: a resolução não ganha código de busca. Ela chama
`match.bank_unit(entry.target_card_instance_id)` e trata `None` como fizzle.

**Rationale**: aquele método foi escrito para isto, e o docstring dele diz
assim: *"É a revalidação de alvo da §6, e `None` não é erro: é a resposta que
autoriza o fizzle. Quem pergunta não precisa saber de qual jogador o alvo é, nem
envolver a chamada em `try`."* Escrever uma segunda busca aqui seria duplicar a
regra e criar o segundo lugar de onde o comportamento pode divergir.

A validação **de lançamento** é outra pergunta e por isso tem outro código: ela
precisa saber de qual jogador o alvo é, porque "aliado" e "inimigo" são
relativos ao lançador. Ela varre o banco esperado primeiro e só consulta
`match.bank_unit()` para separar "banco errado" de "não existe" (D5).

---

## D7 — O aplicador recebe o alvo já resolvido e não sabe de onde a chamada veio

**Decisão**: `apps/game/engine/spell_effect.py`

```python
def apply_spell_effect(
    match: Match,
    caster: PlayerState,
    effect: SpellEffect,
    target: BankUnit | None,
    *,
    catalog: CardCatalog,
) -> None:
```

Nenhum parâmetro diz "pilha" ou "combate", e não existe um. Quem revalida o alvo
é a pilha; o aplicador recebe o `BankUnit` que sobrou da revalidação, ou `None`
quando o efeito não mira nada.

**Rationale**: é FR-029 e FR-030 literais, e a razão está na spec: o feitiço do
defensor da §7.2 resolve imediatamente, sem pilha e sem resposta, e é **o mesmo
efeito com o mesmo resultado**. Um parâmetro de origem — mesmo um booleano —
convida o primeiro `if` que faz os dois caminhos divergirem, e a partir daí
existem duas implementações de cada efeito que precisam ser mantidas iguais à
mão.

O despacho é um `match` exaustivo sobre `SpellEffect`, a união fechada que a
feature 001 escreveu com esta feature em mente: *"União fechada: quando a pilha
de feitiços for implementada, um `match` que esqueça um braço é erro de mypy,
não bug em produção."* FR-032 é essa frase virando teste.

A duração de cada modificador criado vem de `effect.duration`, nunca de um
literal no aplicador (FR-047). É o que faz `PreventUnitDamage` produzir uma
imunidade que o Fim de Rodada varre e `BuffUnitHealth` produzir um bônus que ele
não varre, **sem que o aplicador saiba o que é varrido** — a §8 continua sendo a
única dona dessa regra, e FR-062 vale por construção.

**Alternativas descartadas**:

- *Um método `apply()` em cada classe de efeito, em `cards/effects.py`.* Poria
  regra dentro do catálogo, que é molde imutável compartilhado por todas as
  partidas do servidor, e faria `cards/` importar `match/` — a direção contrária
  à que os dois pacotes declaram nos próprios docstrings.
- *Um `dict[type[SpellEffect], Callable]`.* Perde a exaustividade do mypy, que é
  a única coisa que impede um efeito novo de sumir silenciosamente.
- *O aplicador recebendo `CardInstanceId` e revalidando ele mesmo.* Faria o
  caminho imediato do combate revalidar um alvo que ele acabou de receber do
  jogador, e poria a regra de fizzle num lugar onde fizzle não existe.

---

## D8 — A morte é uma varredura dos dois bancos, não uma checagem do alvo

**Decisão**: depois de aplicar o efeito, `bury_dead_units(match,
catalog=catalog)` varre os dois bancos e move para o cemitério do **dono** toda
unidade cujo dano acumulado alcançou a vida máxima.

**Rationale**: a alternativa óbvia — checar só o alvo que levou dano — precisa
saber de quem é o alvo, e `BankUnit` não sabe: ele contém o `MatchCard` e nada
mais. Descobrir o dono exigiria varrer os jogadores de qualquer jeito, e a
varredura completa faz isso uma vez, por jogador, com o dono em mãos.

O segundo motivo é a §7.3: o dano de combate é **simultâneo**, e a feature
seguinte vai matar várias unidades dos dois lados num evento só. Uma varredura é
a forma que ela já precisa; entregá-la aqui evita que o combate substitua uma
checagem pontual por uma varredura e tenha de reprovar tudo.

A varredura é mais larga que o necessário nesta feature — nenhum dos cinco
efeitos mata alguém que não seja o alvo, e nenhum reduz vida máxima —, e isso é
registrado de propósito: ela não muda nenhum resultado hoje, e é a forma certa
para amanhã.

A comparação é por `card_instance_id`, nunca por `==` entre `BankUnit`:
`BankUnit` é `@dataclass(slots=True)` sem `eq=False`, então duas cópias intactas
da mesma carta são iguais por valor, e uma remoção por valor levaria as duas.

**Alternativa descartada**: *devolver o alvo morto do aplicador e deixar a pilha
enterrá-lo.* Faria o aplicador ter dois retornos — o que ele mudou e o que
morreu — e poria metade da regra de morte fora dele, quebrando FR-045 ("a morte
é verificada assim que o efeito termina").

---

## D9 — Duas quantidades de vida, com dois nomes; "vida efetiva" tem dois sentidos na spec

**Decisão**: `apps/game/engine/unit_vitals.py` expõe

```python
def unit_max_health(unit: BankUnit, *, catalog: CardCatalog) -> int:   # molde + modificadores de vida
def unit_remaining_health(unit: BankUnit, *, catalog: CardCatalog) -> int:  # máxima − dano acumulado
def unit_is_dead(unit: BankUnit, *, catalog: CardCatalog) -> bool:     # restante <= 0
```

**O problema**: a spec usa "vida efetiva" com dois sentidos.

- **FR-034**: *"A vida efetiva de uma unidade MUST ser o valor do molde mais a
  soma dos modificadores de vida, **menos o dano acumulado**."* → é a **restante**.
- **FR-044**: *"Uma unidade cujo **dano acumulado alcança ou ultrapassa a vida
  efetiva** MUST morrer."* → aqui "vida efetiva" só faz sentido como a
  **máxima**; com a restante, a comparação seria `dano >= máxima − dano`.

Os cenários de aceitação confirmam que é a máxima que a morte compara. US5-17
diz "vida efetiva 4 já com 2 de dano" e conclui morte com 5 de dano: 4 é
molde + modificadores, não 4 − 2.

**A resolução não muda nenhum cenário.** As duas formulações são a mesma
desigualdade:

```
dano >= máxima   ⟺   máxima − dano <= 0   ⟺   restante <= 0
```

O que muda é que as duas quantidades passam a ter nomes distintos, e nenhuma
função precisa que o leitor adivinhe qual das duas o nome "vida efetiva"
significa naquela linha. A morte é escrita como `unit_remaining_health(...) <=
0`, que é FR-034 e FR-044 ao mesmo tempo.

`unit_` como prefixo, e não `effective_health`, por causa da regra de nomes
específicos: `health` sozinho aparece no molde (`Unit.health`), no modificador
(`HealthModifier.amount`) e aqui, e um nome que devolve dezenas de ocorrências
de grep não distingue os três.

**`unit_effective_attack` não entra nesta feature.** SACRIFICIAL FIRE escreve um
`AttackModifier`, e nada nesta feature lê ataque — quem lê é a §7.3. A spec não
o pede em nenhum FR. É a decisão oposta à D9 da feature 005, que escreveu um
ramo inalcançável, e a diferença é a mesma que aquela decisão tabelou: lá a §5
**mandava escrever** a condição de saída e a spec a exigia em FR-016; aqui
ninguém pede, e o combate vai precisar da função junto com as regras de bloqueio
que só ele conhece. Os testes de SACRIFICIAL FIRE afirmam o modificador na
unidade — espécie, quantidade e duração —, que é o que esta feature produz.

---

## D10 — `STACK_RESOLUTION` entra na cascata, e o laço continua terminando

**Decisão**: `round_cycle.py` acrescenta a fase ao conjunto de fases automáticas
e um braço ao despacho.

```python
_AUTOMATIC_PHASES = frozenset(
    {MatchPhase.STACK_RESOLUTION, MatchPhase.ROUND_END, MatchPhase.UPKEEP}
)
```

**Rationale**: é a dívida que a feature 005 registrou por escrito e deixou para
esta. O comentário que sai do código dizia: *"`STACK_RESOLUTION` não está aqui
de propósito: a feature que enche a pilha é a que precisa saber esvaziá-la, e
acrescentar a fase sem o corpo da §6 deixaria o laço girando para sempre."* O
corpo existe agora, e a fase entra.

**A terminação continua provável, e o argumento fica mais curto, não mais
longo**: nenhuma fase automática leva a outra que volte à primeira.

| De | Para | Volta |
|---|---|---|
| `STACK_RESOLUTION` | `ACTION` ou `FINISHED` | 1 |
| `ROUND_END` | `UPKEEP` | 1 |
| `UPKEEP` | `ACTION` | 2 |

A Resolução de Pilha **nunca** leva ao Fim de Rodada: ela zera a contagem de
passes antes de devolver a fase de Ação, e é isso que consome os dois passes que
a dispararam (FR-026). O máximo continua sendo duas voltas.

`_settle` e `_run_automatic_phase` passam a receber `catalog`, que a resolução
precisa para ler o efeito do feitiço e a vida do molde. `submit_action` já o
recebe, e já o exige até de um passe que não o usa — a razão está escrita no
docstring dela: *"a porta é uma só, e recebe o que a mais cara das ações
precisa."*

---

## D11 — A pilha para no estado terminal; quem para é o laço, não o aplicador

**Decisão**: `resolve_stack` drena a pilha inteira, e cada entrada é aplicada
**só se** a partida ainda não acabou. A carta vai ao cemitério do lançador nos
dois casos.

```python
def _resolve_top(match: Match, *, catalog: CardCatalog) -> None:
    entry = match.stack.pop()
    _apply_while_the_match_is_live(match, entry, catalog=catalog)
    match.player(entry.caster_user_id).graveyard.append(entry.card)
```

**Rationale**: é a resposta da sessão de esclarecimento (FR-055) posta no lugar
que não a espalha. Duas propriedades saem de graça desta forma:

1. **A pilha esvazia sempre.** O laço é `while match.stack`, e o `pop` acontece
   antes de qualquer decisão. Uma partida terminada não deixa entradas
   penduradas, e FR-055a vale por construção em vez de por um segundo laço de
   limpeza.
2. **O cemitério é uniforme.** Resolvido, fizzlado ou não aplicado por partida
   terminada — a carta vai para o mesmo lugar, na mesma linha. FR-023 tem um
   ponto de escrita só.

**A parada é do laço da pilha, e não do aplicador**, e isso é a decisão. O
aplicador é compartilhado com o combate (D7), e o combate **não tem pilha**: um
feitiço de defensor que encerre a partida não tem "próximo feitiço" para pular.
Pôr a checagem no aplicador daria a ele uma regra que metade dos chamadores não
tem — e daria ao combate um `if` para desativar.

A reabertura da Fase de Ação é o mesmo cuidado, do outro lado:

```python
def _reopen_action_phase(match: Match, initiator_user_id: int) -> None:
    if match.is_over:
        return
    match.consecutive_passes = 0
    match.priority_user_id = initiator_user_id
    match.phase = MatchPhase.ACTION
```

Sem esse `return`, a resolução que terminou a partida a devolveria à Fase de
Ação e apagaria `FINISHED` — o estado que a feature existe para não produzir.

**Alternativas descartadas**:

- *Interromper o `while` com `break` e descartar o resto.* Deixaria a pilha
  cheia num estado terminal, e um estado terminal com pilha pendente é
  exatamente o tipo de coisa que ninguém sabe descrever depois.
- *Verificar a vitória uma vez, no fim da pilha.* Contraria a §10 ao pé da letra
  ("depois de qualquer evento que altere um Nexus") e devolve o resultado que a
  sessão de esclarecimento recusou: um LIFE POTION abaixo de um SACRIFICIAL FIRE
  salvando o lançador.

---

## D12 — O iniciador é lido antes da primeira entrada sair

**Decisão**: `resolve_stack` lê `match.stack[0].caster_user_id` na primeira
linha, antes do laço, e guarda o valor numa variável local.

**Rationale**: FR-024 pede exatamente isto, e a spec explica por quê: *"Como a
pilha esvazia durante a resolução, quem iniciou precisa ser sabido antes de o
primeiro feitiço sair."* Depois do laço, `match.stack[0]` é `IndexError`.

Variável local e **não campo novo no estado**: o iniciador só existe durante a
resolução, que acontece inteira dentro de uma chamada. Um campo
`stack_initiator_user_id` no `Match` teria de ser gravado no lançamento, zerado
na resolução, serializado, e mantido consistente com uma pilha que pode estar
vazia — quatro obrigações para um valor que a pilha já carrega em `stack[0]`.

`resolve_stack` só é chamada com a pilha não vazia: a saída da §5 que a dispara
já verificou `if match.stack`. A pilha vazia é bug de chamador, e é a única
condição que a função assume em vez de checar — como `run_upkeep` assume a fase
de entrada pelo mesmo motivo, e o docstring dela registra isso.

---

## D13 — Nexus sem teto significa nenhuma constante nova

**Decisão**: `RestoreNexus` soma. Não existe `MAX_NEXUS`, não existe `min()`, e
`change_nexus` não conhece limite superior nenhum.

**Rationale**: é a resposta da sessão de esclarecimento (FR-054), e o custo dela
em código é negativo — a alternativa é que teria acrescentado uma constante à
§12 que a nota de domínio não tem.

`STARTING_NEXUS = 20` continua onde está, em `match/player_state.py`, e continua
significando só o valor inicial. Nada nesta feature o lê.

O limite **inferior** também não existe: FR-053 manda preservar o Nexus
negativo. Um `max(0, ...)` apagaria a informação de por quanto o jogador passou
do ponto, que é o que distingue um empate apertado de um estouro.

---

## D14 — `unit_vitals` pergunta, `unit_damage` altera

**Decisão**: dois módulos.

| Módulo | Funções | Natureza |
|---|---|---|
| `unit_vitals.py` | `unit_max_health`, `unit_remaining_health`, `unit_is_dead`, `unit_has_damage_immunity` | consulta pura, não altera nada |
| `unit_damage.py` | `deal_damage_to_unit`, `bury_dead_units` | altera unidade e banco |

**Rationale**: a separação entre perguntar e alterar é a razão de mudar de cada
um. `unit_vitals` muda quando a **conta** de vida mudar — quando o combate
acrescentar `unit_effective_attack`, ou quando uma palavra-chave da §13 mexer na
fórmula. `unit_damage` muda quando o **efeito** do dano mudar — a imunidade da
§7.3, a limpeza da §7.4. Nenhuma das duas razões arrasta a outra.

É também o que mantém os dois pequenos. Juntos passariam de 100 linhas com
quatro responsabilidades misturadas; separados ficam em ~45 cada, e cada teste
tem um alvo óbvio.

`unit_has_damage_immunity` fica em `vitals` e não em `damage` mesmo sendo lida
só por `deal_damage_to_unit`: ela é uma pergunta sobre a unidade, não uma
alteração, e o combate vai fazê-la sem causar dano nenhum ao decidir bloqueio.

---

## D15 — Nenhum teste existente é alterado, exceto dois inventários

**Decisão**: os campos novos do estado — `outcome`, `MatchPhase.FINISHED` — têm o
round-trip provado em `tests/test_spell_state_round_trip.py`, arquivo novo.
`tests/test_match_serialization.py`, da feature 002, não é tocado.

**Rationale**: SC-017 pede que as suítes das features 001, 002 e 005 passem
**sem nenhuma alteração**, e é a mesma disciplina que o plano da feature 005
adotou. Um teste acrescentado a um arquivo existente é uma alteração dele, e
transforma "a suíte antiga passou" numa afirmação que ninguém consegue mais
verificar por inspeção.

> **Correção da Fase 0, apurada na implementação.** A decisão como escrita acima
> era forte demais: **dois testes existentes precisaram mudar**, e os dois pela
> mesma razão — são *inventários* do que o motor tem, e esta feature muda o
> inventário. A previsão original foi feita por grep de comparações de
> dicionário inteiro, e o grep não alcançava nenhum dos dois.
>
> - **`test_match_state.py::test_the_phase_set_is_closed`** compara
>   `[phase.value for phase in MatchPhase]` com a lista literal das fases.
>   `FINISHED` entrou (D1), e a lista ganhou uma linha. O teste existe
>   exatamente para obrigar quem acrescenta uma fase a passar por ele e decidir
>   o que ela significa — ele fez o trabalho dele.
> - **`test_round_cycle.py::test_the_stack_branch_of_the_exit_is_wired`**
>   afirmava `match.phase is MatchPhase.STACK_RESOLUTION` depois de dois passes
>   com a pilha cheia, porque a feature 005 deixou a fase sem corpo de
>   propósito. O docstring dele dizia: *"A cascata para ali de propósito: a
>   feature que enche a pilha é a que precisa saber esvaziá-la."* Isso deixou de
>   ser verdade em D10, e o teste passou a afirmar o outro lado da mesma
>   costura: a cascata atravessa a fase e devolve a partida à Fase de Ação.
>
> Nos dois casos a **regra** não mudou; mudou o fato que o teste inventaria. A
> alternativa — não acrescentar `FINISHED` e não ligar a cascata — é a feature
> inteira. Os dois testes continuam existindo, continuam guardando a mesma
> costura, e o commit que os muda é o mesmo que muda o que eles descrevem.
>
> Nenhum outro arquivo de teste das features 001, 002 e 005 foi tocado.

Três edições em código de produção das features anteriores são inevitáveis e
estão desenhadas para não mexer em teste nenhum:

- **`MatchDocument` ganha a chave `outcome`.** Nenhum teste existente constrói um
  `MatchDocument` literal nem enumera as chaves dele — o único caminho é
  `to_match_document`, e ele é simétrico com `match_from_document`. Verificado
  por grep antes desta decisão.
- **`PlayerView` ganha a chave `outcome`.** `test_player_view.py` compara campos
  nomeados, nunca o dicionário inteiro; a única comparação de conjunto de chaves
  que existe é sobre `view["you"]["hand"][0]`, que não muda.
- **`play_unit.py` passa a usar `card_in_hand` e `ensure_enough_energy` de
  `player_action.py`** em vez das cópias privadas dele (D16).
  `test_play_unit.py` importa de `apps.game.engine`, e o pacote reexporta as
  duas recusas como sempre.

---

## D16 — `card_in_hand` e `ensure_enough_energy` sobem para `player_action.py`

**Decisão**: as duas guardas que jogar unidade e lançar feitiço fazem
**identicamente** deixam de ser privadas de `play_unit.py` e passam a ser
funções do módulo que já é dono da forma da ação. `NotEnoughEnergyError` vai
junto, para o lado da definição que a levanta.

```python
def card_in_hand(actor: PlayerState, card_instance_id: CardInstanceId) -> MatchCard
def ensure_enough_energy(actor: PlayerState, card: MatchCard, cost: int) -> None
```

**Rationale**: é o precedente da própria feature 005, aplicado ao caso que ela
previu. `CardNotInHandError` nasceu em `mulligan.py` e migrou para
`player_action.py` na 005, com a razão escrita no docstring: *"a pergunta — 'a
carta citada está na mão do autor?' — é a mesma no mulligan da §3, na jogada da
§5A e no feitiço da §6 que ainda não existe."* O feitiço existe agora, e a
função que responde a pergunta migra pelo mesmo argumento que a exceção migrou.

`ensure_enough_energy` recebe `cost: int` e não `Unit`: o custo é o único campo
que ela lê, e `Unit` e `Spell` não têm base comum. Passar o inteiro evita um
`Protocol` inventado para dois tipos que já são uma união fechada.

**Alternativa descartada**: *`cast_spell.py` importando as privadas de
`play_unit.py`.* Poria a §5B dependendo do módulo da §5A, que são regras irmãs —
a mesma direção errada que a 005 recusou ao não importar de `mulligan.py`.

---

## Resumo das dependências novas entre módulos

Nenhuma dependência de terceiros. O grafo interno continua um DAG raso:

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
