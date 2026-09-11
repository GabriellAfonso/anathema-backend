# Research: Combate

**Feature**: 007-combat-phase | **Data**: 2026-09-11 | **Fase**: 0

Vinte decisões de desenho, cada uma com a alternativa que foi recusada e a
razão. Nenhuma delas é dúvida aberta: a spec não tem marcador
`[NEEDS CLARIFICATION]`, e as duas escolhas que ela deixou como default estão em
D12 e em D21.

O contexto que todas compartilham: seis features já existem, o combate é a
sétima e a última do motor, e quase tudo que ele precisa foi escrito antes dele
prevendo-o. A pergunta recorrente aqui não é "como fazer", é "o que já existe
para isto, e por que não escrever de novo".

---

## D1 — O estado de combate é campo de `Match`, e vale `None` fora do combate

**Decisão**: `Match` ganha `combat: CombatState | None = None`. `CombatState`
mora em `match/combat_state.py`, ao lado de `spell_stack.py`.

**Razão**: FR-016 exige round-trip pelo Redis, e FR-013 exige que a partida
lembre o pareamento entre duas ações de jogador que podem chegar em workers
diferentes do uvicorn. Estado que precisa atravessar processos é campo do
documento — é o mesmo argumento que `match_state.py` já escreveu para
`next_card_instance_id` e `next_roll_ordinal` ("campo do estado, e não do
processo, porque a partida é lida por qualquer worker").

`None` é ausência, não valor de espera, e é a mesma forma de
`token_holder_user_id` e de `outcome`: fora do combate não existe pareamento, e
inventar um `CombatState` vazio permanente faria FR-017 depender de comparar
listas vazias em vez de comparar com `None`.

**Alternativas recusadas**:

- **Variável local de `submit_action`**, como `initiator_user_id` é em
  `resolve_stack`. Não serve: a pilha resolve inteira dentro de uma chamada, e o
  combate atravessa várias — é justamente a diferença entre os dois.
- **Campo em `PlayerState`** (cada lado guarda os próprios). O pareamento é uma
  relação entre os dois bancos; parti-la em dois lados criaria duas fontes que
  podem divergir, que é o que `Match.awaiting_mulligan_user_ids` e
  `PlayerState.user_id` já recusam cada um no próprio docstring.

---

## D2 — O pareamento é uma lista de pares, nunca um dicionário indexado por identificador

**Decisão**:

```python
@dataclass(slots=True)
class BlockAssignment:
    blocker_card_instance_id: CardInstanceId
    attacker_card_instance_id: CardInstanceId

@dataclass(slots=True)
class CombatState:
    attacker_card_instance_ids: list[CardInstanceId]
    blocks: list[BlockAssignment]
```

**Razão**: é regra explícita do projeto, com a razão já escrita em
`match/documents.py`: *"Chave de objeto JSON é sempre string. O modelo anterior
guardava as mãos e o tabuleiro em dicionários indexados por `user_id` e precisava
converter as chaves de volta para inteiro na leitura — conserto que alguém tinha
de lembrar em toda estrutura nova, e cujo esquecimento não dá erro, dá busca que
não acha nada."* `CardInstanceId` é `int` em tempo de execução, e um
`dict[CardInstanceId, CardInstanceId]` cairia exatamente nessa armadilha.

`test_match_serialization.py::test_no_json_object_is_keyed_by_user_id` já
patrulha o caso do `user_id`. A lista de pares faz o mesmo valer para o
identificador de carta sem precisar de um segundo patrulheiro.

**Alternativa recusada**: `dict[CardInstanceId, CardInstanceId]`. Mais curto de
escrever e uma linha de conversão na leitura — a linha que o projeto inteiro foi
desenhado para não precisar lembrar.

---

## D3 — `CombatState` não guarda quem ataca

**Decisão**: o atacante é `match.token_holder_user_id`, e o defensor é o
oponente dele. Nenhum dos dois é gravado no `CombatState`.

**Razão**: só o dono do token pode declarar ataque (FR-003), e o token não troca
de dono no meio de uma rodada — a troca é passo 2 da §8, no Fim de Rodada. Então
um `attacking_user_id` seria uma cópia de um campo que já existe, e cópia é a
segunda fonte que `PlayerState.user_id` recusa com a razão escrita:
*"duplicar o `user_id` criaria duas fontes que podem divergir"*.

**Consequência aceita**: `token_holder_user_id` é `int | None`, e o combate
precisa estreitá-lo. O estreitamento usa recusa nomeada, pelo precedente exato
de `round_end._swap_token`, que resolve o mesmo `None` impossível com
`NotAParticipantError` em vez de `assert` ou `cast`.

**Alternativa recusada**: gravar `attacking_user_id` no `CombatState` para
evitar o estreitamento. Troca uma linha de estreitamento por um campo que pode
divergir, e por uma chave a mais no documento.

---

## D4 — Cinco braços novos na união de ações, e `player_action.py` não se divide

**Decisão**: `ActionKind` vai de três para oito valores, e a união ganha
`DeclareAttackAction`, `AssignBlockerAction`, `RemoveBlockerAction`,
`CastCombatSpellAction` e `EndDefenseWindowAction`. Tudo em
`player_action.py`, que passa de 347 para ~470 linhas.

**Razão**: a responsabilidade do módulo não muda. O docstring dele já diz o que
ele é — *"a forma de uma jogada que entra no motor, e o que ela precisa provar
antes de qualquer regra específica"* — e oito braços continuam sendo isso. O
mesmo argumento foi feito e aceito na feature 006, quando o módulo cresceu de
~200 para ~290 linhas com `CastSpellAction`.

As **recusas** de cada regra nova **não** entram aqui: vão para o módulo da
regra, como `BankIsFullError` mora em `play_unit.py` e `CardIsNotASpellError` em
`cast_spell.py`. É isso que segura o arquivo abaixo do teto.

E há um argumento que só esta feature pode fazer: **não existe um nono braço**.
A §5 tem quatro ações e a §7.2 tem quatro; as duas listas fecham aqui, e o
Fluxo de Partida não tem uma nona ação em lugar nenhum.

**Alternativas recusadas**:

- **Partir em `player_action.py` + `combat_action.py`.** A união precisa
  enxergar os dois lados, e os braços do combate precisam de `ActionKind` — o
  que dá ciclo de import, a menos que um terceiro módulo exista só para o enum.
  Três módulos, um deles com 25 linhas e um enum dentro, para resolver um
  arquivo de 470 linhas que está abaixo do teto.
- **Fundir `AssignBlockerAction` e `RemoveBlockerAction`** num só braço com
  `attacker_card_instance_id: CardInstanceId | None`. Recusado: as duas ações
  têm recusas diferentes (FR-028 contra FR-032), e o `None` viraria um
  discriminante escondido dentro de um braço — exatamente o que a união fechada
  existe para não ter.
- **Reusar `CastSpellAction` com `{ACTION, COMBAT}`.** Recusado pelo código que
  já está escrito: o docstring de `CastSpellAction` diz *"`{ACTION}` e não
  `{ACTION, COMBAT}`: o feitiço do defensor da §7.2 resolve imediatamente, sem
  pilha e sem chance de resposta, e é outra ação — não esta com uma fase a
  mais."* A feature 006 previu esta decisão e a escreveu.

---

## D5 — A prioridade que não troca é `keeps_priority`, declarada por braço

**Decisão**: cada braço da união declara
`keeps_priority: ClassVar[bool]`, sem default, e
`round_cycle._pass_priority` ganha duas linhas:

```python
def _pass_priority(match: Match, action: PlayerAction) -> None:
    if action.keeps_priority:
        return
    match.priority_user_id = match.opponent_of(action.actor_user_id).user_id
```

Os quatro braços da §5 declaram `False`; os quatro da §7.2 declaram `True`.

**Razão**: é FR-021 tornada estrutural. A exceção da §7.2 é propriedade **da
ação**, do mesmo jeito que `allowed_phases` já é — e `player_action.py` já
escreveu a razão de `allowed_phases` morar ali: *"Mora na ação, e não numa
cadeia de `if` dentro da guarda, porque a §5 escreve a pergunta como 'a fase
atual permite **esta** ação'."* A pergunta aqui é gêmea: "esta ação devolve a
vez?".

Sem default, porque `allowed_phases` também não tem: um braço novo que esqueça
de responder é erro de mypy, e a resposta errada por omissão seria justamente a
que vaza a exceção para a Fase de Ação.

**Alternativas recusadas**:

- **`if match.phase is MatchPhase.COMBAT: return` dentro de `_pass_priority`.**
  Funciona e é uma linha mais curta. Recusado porque põe a exceção na função
  comum: quem ler `_pass_priority` passa a precisar saber da §7.2, e o dia em
  que uma ação de combate precisar trocar a prioridade, a condição vira duas.
- **Trocar a prioridade e devolvê-la em seguida** (troca e re-troca dentro de
  cada ação da janela). Recusado: a partida passaria por um estado intermediário
  em que a prioridade é do atacante, e um erro no meio do caminho a deixaria lá.

---

## D6 — `COMBAT` não entra em `_AUTOMATIC_PHASES`

**Decisão**: o conjunto de fases automáticas da cascata continua sendo
`{STACK_RESOLUTION, ROUND_END, UPKEEP}`. `COMBAT` fica de fora.

**Razão**: fase automática é a que a cascata atravessa sem input. O Combate
**espera** o defensor — é o único ponto do jogo em que a partida para numa fase
que não é a Fase de Ação e isso é correto. FR-070 não pede que o Combate seja
atravessado; pede que nenhuma ação devolva a partida parada numa fase
automática, e que a ação que encerra a janela devolva a partida esperando ação.
As duas coisas valem sem tocar em `_AUTOMATIC_PHASES`.

Quem dispara o dano, a limpeza e a volta é a ação `EndDefenseWindowAction`,
dentro de `_apply_action` — antes, portanto, de `_exit_action_phase` e de
`_settle`, que encontram a partida já na Fase de Ação e não fazem nada.

**Alternativa recusada**: pôr `COMBAT` entre as automáticas e deixar a cascata
resolvê-lo. Não fecha: `_settle` roda até a partida sair das fases automáticas,
e o Combate precisa **ficar** parado esperando o defensor. A cascata entraria em
laço infinito ou precisaria de uma condição de saída própria — que é a mesma
coisa que não ser automática.

---

## D7 — Declarar ataque zera a contagem de passes

**Decisão**: `declare_attack` faz `match.consecutive_passes = 0`, como
`play_unit` e `cast_spell` já fazem.

**Razão**: a §5 conta passes **consecutivos**, e uma jogada quebra a sequência —
é a frase que os docstrings de `play_unit` e `cast_spell` já escrevem. Declarar
ataque é jogada.

**Consequência que carrega a feature**: com os passes em 0 na entrada do combate
e nenhuma ação da janela os incrementando, `_exit_action_phase` fica **inerte**
durante todo o combate — ela só faz alguma coisa com dois passes consecutivos.
Nenhuma linha dela muda, e ainda assim não existe caminho em que o combate caia
no Fim de Rodada ou na Resolução de Pilha. É a mesma economia que a feature 005
conseguiu ao escrever a saída da fase antes de haver o que resolver.

---

## D8 — O atacante é espectador pela guarda de prioridade que já existe

**Decisão**: não existe guarda "o autor é o defensor" em lugar nenhum. Durante o
combate a prioridade é do defensor, e `ensure_action_allowed` recusa toda ação
do atacante com `NotYourPriorityError`.

**Razão**: FR-022 pede recusa citando que a prioridade é do defensor, e é
literalmente o que `NotYourPriorityError` já escreve: *"user 9 cannot act in
match 'm-1': priority belongs to user 7"*. Uma guarda nova diria a mesma coisa
com outro nome, e teria de ser repetida nas quatro ações da janela.

Vale também para a simetria: o defensor tentando uma ação da §5 durante o
combate cai em `PhaseForbidsActionError`, porque `{ACTION}` não contém `COMBAT`.
As duas metades de FR-023 e as de FR-024 saem das duas guardas que já existem,
na ordem que a feature 005 congelou.

**Alternativa recusada**: `NotTheDefenderError`. Mais explícita na mensagem, e
redundante com a guarda 2 em todos os casos alcançáveis.

---

## D9 — O estreitamento de `Match.combat` mora no pacote de estado

**Decisão**: `Match` ganha

```python
def ongoing_combat(self) -> CombatState: ...
```

que devolve o `CombatState` ou levanta `MatchIsNotInCombatError`, definida em
`match/match_state.py` ao lado de `NotAParticipantError`.

**Razão**: é a mesma forma e a mesma razão de `Match.player()`, que levanta
`NotAParticipantError` para um `user_id` que não joga. `match_state.py` diz de
si mesmo que não decide regra — e responder "qual é o combate em curso, e recusa
se não há" não é regra, é a mesma pergunta que `player()` faz sobre jogador.

Três módulos do motor precisam do estreitamento (`blocker_pairing`,
`cast_combat_spell` pelo alvo, `combat_damage`). Escrevê-lo em cada um seria
duplicar; pô-lo num quarto módulo do motor seria um módulo só para um `if`.

`MatchIsNotInCombatError` não herda de `IllegalActionError` pela razão que
`NotAParticipantError` já tem escrita: *"mora em `apps.game.match` e não pode
herdar daqui sem inverter a dependência entre o pacote de estado e o de
regra"*.

**Alternativa recusada**: `Match.combat` continuar sendo lido cru e cada regra
fazer `if combat is None: raise`. Três cópias da mesma recusa impossível.

---

## D10 — As guardas de lançamento de feitiço sobem para um módulo próprio

**Decisão**: novo módulo `engine/spell_cast_guards.py`, que recebe de
`cast_spell.py`:

- as cinco recusas (`CardIsNotASpellError`, `SpellTakesNoTargetError`,
  `SpellNeedsTargetError`, `WrongSpellTargetSideError`,
  `SpellTargetNotOnBattlefieldError`);
- as quatro guardas da §5B, agora numa porta só:
  `validated_spell_cast(...) -> ValidatedSpellCast`, com `card`, `spell` e
  `target: BankUnit | None`.

`cast_spell.py` encolhe para a regra da §5B (descontar, tirar da mão, empilhar).
`cast_combat_spell.py` usa a mesma porta.

**Razão**: FR-040 exige as mesmas guardas na mesma ordem nos dois caminhos, e a
constituição proíbe duplicar. O precedente é exato e é do próprio projeto: a
feature 006 subiu `card_in_hand` e `ensure_enough_energy` de `play_unit.py` para
`player_action.py` quando a §5B passou a fazer as mesmas perguntas — e a feature
005 tinha subido `CardNotInHandError` de `mulligan.py` pelo mesmo motivo.

A porta devolve o `BankUnit` do alvo, e não só valida o lado. O caminho da pilha
ignora o valor; o caminho do combate precisa dele para aplicar o efeito na hora.
Resolver o `BankUnit` também **apaga** `cast_spell._owner_of`, que fazia a
mesma varredura que `Match.bank_unit` já faz.

**Prova de que o movimento não mudou comportamento**: `test_cast_spell.py`, 559
linhas, passa **sem uma linha alterada**. As recusas, a ordem e as mensagens são
as mesmas; só o arquivo em que as classes moram mudou.

**Alternativa recusada**: deixar tudo em `cast_spell.py` e importar de lá. Sem
módulo novo e com menos movimentação — mas põe o módulo cujo docstring diz "a
ação B da §5" como dono das guardas de uma ação que não é da §5.

---

## D11 — O feitiço imediato manda a carta ao cemitério depois de aplicar o efeito

**Decisão**: `cast_combat_spell` desconta a energia, tira a carta da mão,
**aplica o efeito** e só então põe a carta no cemitério do lançador.

**Razão**: é a ordem que `stack_resolution._resolve_top` já usa — aplica, e
depois `graveyard.append`. SC-008 exige resultado idêntico **campo a campo**
entre os dois caminhos, e o cemitério é uma lista ordenada: se o combate
enterrasse a carta antes de aplicar, uma unidade morta pelo efeito entraria
depois dela, e a ordem dos dois cemitérios divergiria entre os caminhos por uma
diferença que nenhum requisito pede.

É o tipo de detalhe que só aparece quando alguém compara os dois caminhos — e
SC-008 existe para que alguém compare.

---

## D12 — `unit_effective_attack` entra em `unit_vitals.py`, com piso em 0

**Decisão**:

```python
def unit_effective_attack(unit: BankUnit, *, catalog: CardCatalog) -> int:
    """O ataque do molde mais a soma dos modificadores de ataque, nunca abaixo
    de 0."""
```

**Razão do lugar**: o módulo pede por escrito. `unit_vitals.py` termina com
*"`unit_effective_attack` **não mora aqui ainda**: SACRIFICIAL FIRE escreve o
modificador de ataque, e quem lê ataque é a §7.3. Ela entra com o combate, junto
das regras de bloqueio que só ele conhece."* É o combate chegando ao lugar que
aquele texto reservou, exatamente como `unit_vitals.py` foi o motor chegando ao
lugar que `BankUnit.damage_taken` reservou.

**Razão do piso** (um dos dois defaults que a spec registrou): `AttackModifier`
aceita `amount` negativo por construção — o docstring dele diz *"`amount`
negativo é como se reduz ataque"* — e nenhuma das cinco cartas do MVP produz um.
Sem piso, um ataque efetivo negativo passaria por `deal_damage_to_unit`
**reduzindo** `damage_taken` (curando a unidade) e por `change_nexus`
**somando** Nexus. Nenhuma das duas é regra da §7, e as duas seriam bugs que
nenhum teste do MVP alcança.

O piso fica no ataque efetivo e **não** dentro de `deal_damage_to_unit`: aquele
módulo é compartilhado com SUMMONED AX, cujo `amount` já é positivo por
construção, e pôr o piso lá seria escrever no caminho da §5B uma regra da §7.3.

**Alternativa recusada**: deixar sem piso e confiar no catálogo. O catálogo do
MVP não produz o caso, mas a palavra-chave de redução de ataque está na §13 e
chegaria por este caminho.

---

## D13 — O dano é planejado inteiro antes de ser aplicado

**Decisão**: `resolve_combat_damage` monta primeiro a lista de golpes
(`(BankUnit, quantidade)`) e o total de dano ao Nexus, e só então aplica. Nada é
escrito durante a leitura.

**Razão**: FR-051 é sobre simultaneidade, e simultaneidade é uma propriedade da
**ordem de leitura**, não da de escrita. Aplicar enquanto percorre daria o mesmo
resultado hoje — dano acumulado não altera ataque efetivo, e `bury_dead_units`
só roda depois —, mas o resultado dependeria de nenhuma dessas duas coisas
mudar. Com o planejamento separado, a independência de ordem é estrutural: todo
o ataque efetivo é lido antes da primeira escrita.

É o mesmo movimento que `round_end._lasting_modifiers` faz ao devolver lista
nova *"para não mutar durante a leitura"*.

**Alternativa recusada**: aplicar em linha, no laço. Uma função a menos, e a
garantia de FR-051 passa a ser "não acontece de dar diferente" em vez de "não
pode dar diferente".

---

## D14 — Um par só troca dano se as duas unidades estiverem em campo

**Decisão**: na resolução, para cada atacante declarado:

| Atacante em campo | Bloqueador declarado | Bloqueador em campo | Resultado |
|---|---|---|---|
| não | — | — | nada acontece (FR-053) |
| sim | não | — | dano ao Nexus do defensor (FR-050) |
| sim | sim | sim | troca de dano, nada ao Nexus (FR-049) |
| sim | sim | não | nada acontece, e **nada ao Nexus** |

**Razão**: a terceira linha é a §7.3 literal, e a primeira é FR-053. A quarta
não é alcançável com as cinco cartas do MVP — o atacante é espectador e não pode
matar um bloqueador, e nenhum feitiço do defensor mata unidade do próprio dono —
mas precisa de resposta escrita porque o código tem de ter um braço.

A resposta escolhida é a que a §7.3 sustenta: *"Bloqueado: (...) Nenhum dano
chega ao Nexus."* Estar bloqueado é propriedade da **declaração**, não da
sobrevivência do bloqueador. É também a simétrica da regra do bloqueador órfão,
que a §7.3 escreve: quando um dos dois some, o outro não troca dano com
ninguém.

**Alternativa recusada**: tratar o bloqueador ausente como "atacante
desbloqueado" e mandar o dano ao Nexus. Também defensável, e assimétrica com a
regra do órfão — o mesmo fato (um dos dois sumiu) teria duas respostas opostas
conforme qual dos dois sumiu.

---

## D15 — A apuração única da §10 mora numa função nova de `victory.py`

**Decisão**: `victory.py` ganha

```python
def change_nexus_simultaneously(
    match: Match, amount_by_player: Sequence[tuple[PlayerState, int]]
) -> None:
```

que altera todos os Nexus citados e chama `check_victory` **uma vez**, depois de
todos. `change_nexus` passa a ser essa mesma função para um jogador só; as duas
escrevem por um privado comum.

**Razão**: FR-058, FR-059 e FR-061 juntas. O Nexus continua tendo um escritor
só, e a diferença entre as duas portas públicas é exatamente a que o docstring
de `victory.py` já antecipou:

> `change_nexus` altera **um** Nexus e verifica logo em seguida. É o que a §5B
> usa. `check_victory` só verifica. É o que a §7.3 vai usar, em que o dano de
> combate é simultâneo e altera os dois Nexus antes de existir um resultado a
> apurar.

O que a feature 006 não podia prever é que "alterar os dois" precisaria de uma
porta, já que `change_nexus` apura a cada chamada. `check_victory` continua
pública e continua sendo o que apura; a novidade é a alteração múltipla que a
chama uma vez.

**Alternativa recusada**: o combate escrever `player.nexus` direto e chamar
`check_victory` depois. Duas linhas a menos e uma frase a menos verdadeira: o
docstring de `change_nexus` diz que ela é *"a única porta que escreve Nexus"*, e
um segundo escritor fora do módulo tornaria isso falso sem que nada quebrasse.

---

## D16 — O combate sempre passa os dois jogadores para a apuração, mesmo com 0

**Decisão**: `resolve_combat_damage` chama

```python
change_nexus_simultaneously(match, ((defender, -total), (attacker, 0)))
```

sempre — inclusive quando o total é 0 e inclusive para o atacante, que nunca
recebe dano de combate (FR-057).

**Razão**: faz FR-058 valer **literalmente** — "os dois Nexus alterados antes de
a §10 ser apurada" deixa de ser uma promessa sobre o caso de dois lados e passa
a ser o que o código faz em todo combate. E é o que torna FR-060 testável: um
estado montado com o Nexus do atacante já em 0 ou menos e a partida ainda
correndo produz o empate por este caminho, sem teste nenhum precisar de uma
carta que não existe.

A soma de 0 não é operação morta: é a afirmação de que o atacante participou do
mesmo cálculo. `check_victory` varre `match.players` de qualquer jeito, então o
resultado seria o mesmo — o que muda é que a forma da chamada passa a dizer a
regra.

**Alternativa recusada**: citar só o defensor. Menor, e deixa FR-058 sem
correspondente no código.

---

## D17 — A invariante de combate é unidirecional

**Decisão**: vale `phase is COMBAT ⟹ combat is not None`. A recíproca **não**
vale: uma partida terminada durante a janela do defensor (FR-062) fica com
`phase is FINISHED` e o `CombatState` intacto.

**Razão**: FR-062 pede que o estado continue íntegro e serializável, e essa é a
leitura honesta do que acontece — o combate **não terminou**, foi interrompido
por uma partida que acabou. Congelar o estado onde ele parou é o registro fiel
disso, e nenhuma ação é aceita depois para observá-lo de forma inconsistente.

FR-067 ("terminado o combate, o estado desaparece") continua valendo no caminho
em que o combate termina: `end_combat` limpa `match.combat` **antes** do
`return` que a partida terminada provoca, então um combate que encerra a partida
pelo próprio dano também sai sem estado. O único estado que sobrevive é o do
combate que nunca resolveu.

**Alternativa recusada**: limpar `match.combat` também na interrupção, para
manter a bicondicional. Recusado: apagaria a única informação que distingue
"combate resolvido" de "combate interrompido" num estado que a spec manda
preservar.

---

## D18 — Seis módulos novos no `engine/`, um por regra

**Decisão**:

| Módulo | Responsabilidade | Seção |
|---|---|---|
| `declare_attack.py` | a quarta ação da Fase de Ação e as sete recusas dela | §5C, §7.1 |
| `blocker_pairing.py` | atribuir e remover bloqueador, e as cinco recusas | §7.2 |
| `spell_cast_guards.py` | as quatro guardas de lançamento, compartilhadas | §5B, §7.2 |
| `cast_combat_spell.py` | o feitiço que resolve na hora | §7.2 |
| `combat_damage.py` | o cálculo e a aplicação do dano simultâneo | §7.3 |
| `combat_cleanup.py` | limpeza, apuração e volta à Fase de Ação | §7.4, §7.5 |

**Razão**: é o desenho que o `engine/` já tem — plano, um módulo por regra, com
o grafo de imports sendo um DAG raso. Cada um destes seis tem uma razão própria
para mudar: as recusas da declaração mudam com a §5C, o pareamento muda com a
regra de bloqueio, a fórmula do dano muda com palavras-chave, a limpeza muda com
a ordem da §7.4.

`blocker_pairing.py` guarda duas funções (`assign_blocker`, `remove_blocker`)
porque elas são os dois lados da mesma invariante 1:1 e compartilham as buscas;
separá-las poria a invariante em dois arquivos.

**Alternativa recusada**: um `combat.py` único com tudo. Passaria de 500 linhas
com cinco responsabilidades, e é o "god file" que a constituição nomeia.

---

## D19 — `MatchDocument` e `PlayerView` ganham `combat`

**Decisão**: uma chave nova em cada, do tipo `CombatDocument | None`, com
`CombatDocument` espelhando `CombatState` e `BlockAssignmentDocument`
espelhando `BlockAssignment`.

**Razão**: o documento, por FR-016. A visão, porque o pareamento é **informação
pública** — os dois jogadores veem quem ataca quem, e sem isso o cliente não tem
como desenhar o combate. É a mesma decisão que pôs `stack` na visão inteira,
enquanto a mão do oponente vira contagem: pilha e combate são fatos revelados; a
mão não é.

Sem migration, pela razão que `MatchDocument` já escreve de si mesmo: a partida
vive no Redis como JSON e o compare-and-swap de `store.py` não versiona esquema.
A chave é obrigatória no `TypedDict`, com valor `None` — um `total=False`
deixaria o resto do documento igualmente opcional, que é o argumento que a
feature 006 já usou para `outcome`.

---

## D20 — Nenhum arquivo de teste existente precisa mudar

**Decisão**: a previsão é que os 40 arquivos de teste atuais passem sem
alteração, e SC-023 continua autorizando a mudança de um inventário caso algum
apareça.

**Razão**: os inventários que existem foram conferidos um a um.

- `test_match_state.py::test_the_phase_set_is_closed` lista os valores de
  `MatchPhase`. **Não muda**: esta feature não acrescenta fase — `COMBAT` está
  lá desde a feature 002.
- `test_player_action.py::test_each_action_declares_its_own_kind` e
  `::test_both_actions_of_this_feature_belong_to_the_action_phase` afirmam sobre
  `PlayUnitAction` e `PassAction` nomeadamente, não sobre a união inteira.
  **Não mudam.**
- `test_player_view.py::test_the_shared_round_fields_appear` lê as chaves por
  índice, não compara o conjunto delas. **Não muda** com uma chave nova.
- `test_match_serialization.py` não inventaria as chaves do documento; o
  round-trip passa pela igualdade de `MatchDocument`, e `combat: None` atravessa
  como `None`. **Não muda.**
- `test_cast_spell.py` é o que D10 movimenta, e é justamente a prova de que o
  movimento foi só de arquivo. **Não muda.**

Se um inventário aparecer na implementação, ele muda e a mudança é registrada —
foi o que a feature 006 fez com os dois que ela encontrou.

---

## D21 — A partida que termina durante a janela não resolve o dano

**Decisão** (o segundo default que a spec registrou): se um feitiço do defensor
encerra a partida no meio da janela, nenhuma ação seguinte é aceita e o dano do
combate nunca é resolvido.

**Razão**: cai fora sozinho, sem nenhuma linha escrita para isso.
`apply_spell_effect` chama `change_nexus`, que apura a §10 e põe a partida em
`FINISHED`; a partir daí `ensure_action_allowed` levanta `MatchIsOverError` em
toda ação, inclusive a que encerraria a janela. É o mesmo mecanismo, herdado sem
mudança, que a feature 006 descreve: *"`FINISHED` não está entre as automáticas,
então a partida encerrada para o laço sem que ele precise saber da §10"*.

É também a decisão que a feature 006 tomou para a pilha, pelo mesmo argumento —
assim que a §10 encontra um Nexus em 0 ou menos, nada mais é aplicado.

**Alcançável**: SACRIFICIAL FIRE cobra 8 de Nexus do lançador, então um defensor
com 8 ou menos que o lance se derrota no meio da própria janela.

**Alternativa recusada**: resolver o dano mesmo assim, para "terminar o que
começou". Precisaria de um caminho que aceita ação numa partida terminada, que é
exatamente o que FR-052 da feature 006 proíbe.

---

## O que esta feature confirma, e que por isso não muda

Quatro textos escritos por features anteriores prevendo o combate. Nenhum vira
código novo; todos viram chamada.

- **`unit_damage.bury_dead_units`**: *"o dano da §7.3 é simultâneo: o combate vai
  matar várias unidades dos dois lados num evento só, e esta é a forma que ele
  já precisa."* Chamada uma vez em `combat_cleanup`, sobre os dois bancos.
- **`victory.check_victory`**: *"É o que permite ao combate chamá-la depois do
  dano simultâneo sem contar quantas vezes já foi chamada."* D15 usa exatamente
  essa propriedade.
- **`spell_effect.apply_spell_effect`**: *"no combate (§7.2) o feitiço do
  defensor vai chamar o mesmo, com o alvo que acabou de receber, sem pilha e sem
  chance de resposta."* `cast_combat_spell` é essa chamada, e não recebe
  parâmetro nenhum dizendo de onde veio.
- **`unit_vitals.unit_has_damage_immunity`**: *"Mora entre as consultas e não
  entre as alterações porque é pergunta — o combate vai fazê-la sem causar dano
  nenhum, ao decidir bloqueio."* Na verdade quem a faz é `deal_damage_to_unit`,
  já; o combate a herda de graça e FR-055 vale sem uma linha nova.
