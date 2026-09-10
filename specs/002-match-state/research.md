# Fase 0 — Pesquisa e decisões de desenho

**Feature**: Estado de Partida (`002-match-state`)
**Data**: 2026-09-09

A Technical Context não deixou nenhum `NEEDS CLARIFICATION`: a stack está
fixada pela constituição e as cinco perguntas de modelagem foram fechadas na
sessão de clarificação registrada na spec. O que este documento resolve são as
escolhas de implementação que a spec deliberadamente não fez.

As decisões já fechadas na spec entram aqui só como referência de origem:

| Já decidido em *Clarifications* | Onde é implementado |
|---|---|
| Identificador de instância é inteiro sequencial e opaco | D1 |
| Espaço de identificadores único na partida | D1 |
| Dano acumulado, não vida atual | D4 |
| Modificador como união fechada de tipos | D5 |
| Jogadores em lista de dois, sem chave por `user_id` | D6 |

---

## D1 — Como o identificador de instância é cunhado

**Decisão**: `CardInstanceId = NewType("CardInstanceId", int)`, cunhado por
`Match.mint_card_instance_id()`, que devolve `next_card_instance_id` e o
incrementa. O contador nasce em 1 e é campo do `Match`.

**Rationale**: `NewType` é o mesmo instrumento que `CardId` já usa em
`cards/card.py`, pelo mesmo motivo declarado lá — os dois são inteiros e viajam
nos mesmos payloads, e `NewType` custa nada em execução e transforma a troca em
erro de mypy. Aqui são três inteiros no mesmo payload (`user_id`, `card_id`,
`card_instance_id`), então o risco é maior, não menor.

O contador como campo do `Match`, e não como variável de módulo ou contador
global, é o que faz FR-015 valer: o estado inteiro vive no Redis e é lido por
qualquer worker do uvicorn. Um contador de processo daria números repetidos
entre workers.

**Alternativas consideradas**:

- **UUID4 por carta**: dispensa contador e é único sem coordenação. Custa 36
  bytes por carta × 80 cartas em cada gravação, e torna todo teste ilegível
  (`assert unit.card.card_instance_id == UUID("...")`) ou dependente de mock de
  aleatoriedade. Rejeitado: o requisito é unicidade **na partida**, e o escopo
  de unicidade global do UUID não compra nada.
- **`f"{card_id}-{letra}"`**, formato de um jogo anterior do maintainer:
  embute o `card_id` no identificador, o que convida a `split("-")[0]` em vez
  de ler o campo — a mesma classe de erro que `card.py` já proibiu para as
  faixas de `card_id`. Além disso o alfabeto de sufixos é o limite de 3 cópias
  por deck vazando para o espaço de identidade. Rejeitado, e registrado como
  descartado nas *Clarifications* da spec.
- **Contador por jogador**: reintroduz colisão entre os dois lados e obriga a
  chave composta `(user_id, card_instance_id)` na pilha e no combate.
  Rejeitado nas *Clarifications*.

---

## D2 — `BankUnit` contém `MatchCard`, não copia seus campos

**Decisão**: composição.

```python
@dataclass(slots=True)
class BankUnit:
    card: MatchCard
    damage_taken: int
    modifiers: list[UnitModifier]
```

**Rationale**: é a forma de fazer FR-012 ("o identificador não muda ao trocar
de zona") ser verdade por construção em vez de por disciplina. Mover uma
unidade morta para o cemitério é `graveyard.append(unit.card)` — o mesmo objeto,
o mesmo identificador, e o dano e os modificadores ficam para trás sem que
ninguém precise lembrar de zerá-los. Invocar do banco é
`bank.append(BankUnit(card=hand.pop(i), damage_taken=0, modifiers=[]))`.

Também é o que faz FR-018 ("carta na mão não carrega dano") ser estrutural: um
`MatchCard` simplesmente não tem onde guardar dano.

**Alternativas consideradas**:

- **Achatar `card_instance_id` e `card_id` dentro de `BankUnit`**: JSON um
  nível mais raso e acesso mais curto (`unit.card_instance_id`). Custa duplicar
  dois campos e transformar cada mudança de zona em uma cópia manual campo a
  campo, que é exatamente onde um identificador se perde. Rejeitado.
- **`BankUnit` herdando de `MatchCard`**: dá acesso curto sem duplicar. Herança
  entre dataclasses com `slots=True` funciona, mas passa a permitir usar um
  `BankUnit` onde se espera um `MatchCard` — e aí uma unidade com dano pode ser
  enfiada na mão sem que o mypy reclame. Rejeitado: a distinção entre carta e
  carta-em-campo é a invariante, e herança a apaga.

---

## D3 — `Match` como dataclass mutável, com `players` em tupla de dois

**Decisão**: `@dataclass(slots=True)` (mutável), com
`players: tuple[PlayerState, PlayerState]`.

**Rationale**: mutável porque o motor vai mutar — jogar carta, aplicar dano,
avançar fase. Congelar obrigaria a reconstruir o estado inteiro a cada ação, e
a spec já registra que a mutação vem depois, não que ela não vem. `slots=True`
fecha a porta de atributo novo por atribuição, que é o que sobra de proteção
quando não há `frozen`.

A tupla de dois codifica a aridade no tipo: `players[0]` e `players[1]` sempre
existem, e mypy recusa uma lista de três. É mais barato que uma validação em
tempo de execução e não pode ser burlado.

**Alternativas consideradas**:

- **`list[PlayerState]`**, como hoje: aceita zero, um ou três jogadores, e
  cada leitor precisa acreditar que são dois. Rejeitado.
- **`frozen=True` com métodos que devolvem um `Match` novo**: puro e fácil de
  testar, mas o `MatchStore` faz read-modify-write, e a spec registra que a
  atomicidade disso é problema futuro de script Lua. Estilo funcional não
  resolve esse problema e cobra em todas as features seguintes. Rejeitado.

---

## D4 — `damage_taken` em vez de `current_health`

**Decisão**: a unidade guarda dano acumulado. Vida efetiva, ataque efetivo e
morte são derivados, e derivá-los é da feature do motor.

**Rationale**: modificador é alteração com duração — entra na lista, sai da
lista. Dano não tem duração e não expira, então não cabe na lista. Guardar
vida atual absoluta obriga a desfazer na mão a expiração de um buff de vida
temporário, e o resultado passa a depender da ordem dos eventos: se a unidade
tomou dano enquanto o buff estava ativo, subtrair a quantidade do buff mata ou
não mata dependendo de quando cada coisa aconteceu. Com dano acumulado,
expirar é remover da lista e a conta se refaz sozinha.

No MVP a diferença não aparece — `BuffUnitHealth` é `PERMANENT` e
`PreventUnitDamage` não tem quantidade — mas o formato certo custa o mesmo
agora e uma migração depois.

**Alternativas consideradas**:

- **`current_health` absoluto**: mais direto de ler em log e em teste.
  Rejeitado pelo acima.
- **Guardar os dois** (`current_health` e `max_health` materializados): duas
  fontes de verdade que podem divergir, e a segunda é derivável. Rejeitado.

---

## D5 — Discriminante da união de modificadores no JSON

**Decisão**: cada modificador serializa com um campo `modifier_kind`, valor de
uma `ModifierKind(StrEnum)` — `"attack"`, `"health"`, `"damage_immunity"`. A
desserialização é um `match` sobre esse campo, exaustivo.

**Rationale**: uma união de dataclasses não sobrevive ao JSON sozinha —
`{"amount": 2, "duration": "permanent"}` serve tanto para `AttackModifier`
quanto para `HealthModifier`. O discriminante é obrigatório, e nomeá-lo
`modifier_kind` em vez de `kind` ou `type` mantém a regra de nome específico e
greppável da constituição.

A duração reaproveita `EffectDuration` de `apps.game.cards.effects`: os valores
são exatamente os dois que a §8 precisa, e um enum paralelo seria duplicação
com risco de divergir.

**Alternativas consideradas**:

- **Um campo `attribute` em string livre**, sem enum: `"atack"` escrito errado
  passa reto. Rejeitado, e registrado nas *Clarifications*.
- **Nome da classe como discriminante** (`{"modifier_kind": "AttackModifier"}`):
  amarra o formato gravado ao nome do símbolo em Python, então renomear a
  classe invalida partidas vivas no Redis. Rejeitado.

---

## D6 — Busca de jogador e de unidade alvo

**Decisão**: `Match.player(user_id)` varre a tupla de dois e levanta
`NotAParticipantError` citando o `user_id`; `Match.bank_unit(card_instance_id)`
varre os dois bancos e devolve `BankUnit | None`.

**Rationale**: sem chave por `user_id` (decisão da spec), a busca é varredura —
de dois elementos, e de no máximo 12 unidades pelo teto de banco da §12. Não há
o que otimizar, e um índice seria estado derivado a manter em sincronia.

`player()` levanta e `bank_unit()` devolve `None` de propósito, e a diferença é
o ponto: pedir o jogador de um `user_id` que não joga é erro de programação —
o gate de participante já deveria ter fechado o socket. Perguntar por um alvo
que sumiu é a **pergunta normal** da §6, e a resposta negativa é o fizzle.
Levantar ali obrigaria todo call site a envolver a pergunta em `try`.

Isso diverge do catálogo, onde `UnknownCardError` é sempre levantado —
`catalog.py` registra o porquê: "quem pede uma carta já decidiu que ela deveria
existir". Quem pergunta por um alvo decidiu o contrário.

**Alternativas consideradas**:

- **`dict[CardInstanceId, BankUnit]` como índice no `Match`**: busca em tempo
  constante. Custa manter o índice sincronizado em toda mudança de zona, e um
  índice fora de sincronia dá o bug que esta feature existe para impedir —
  acertar a unidade errada. Rejeitado; 12 elementos não justificam.
- **`bank_unit()` devolvendo `(PlayerState, BankUnit) | None`**: o motor vai
  querer saber de quem é a unidade para decidir aliado contra inimigo. Adiado:
  decidir isso é regra, e a busca do dono é uma linha a partir da unidade.
  Registrado em *Out of Scope* na spec.

---

## D7 — Serialização em funções livres, não em métodos

**Decisão**: `serialization.py` com um par de funções por tipo —
`to_match_document(match)` / `match_from_document(document)`, e assim por
diante. `store.py` passa a chamá-las diretamente.

**Rationale**: a serialização é a única parte que precisa conhecer o formato
gravado, o discriminante de união e a ordem das listas. Concentrá-la num módulo
mantém os tipos de domínio sem nenhuma menção a JSON, e evita que a lógica de
`match`/`case` da união se espalhe por três classes.

O custo é honesto: `store.py` muda dois call sites, de `match.as_dict()` para
`to_match_document(match)`. FR-039 pede que os **chamadores do store** não
mudem, e eles não mudam — o consumer continua chamando `store.save(match)`.

**Alternativas consideradas**:

- **`as_dict()` / `from_dict()` como métodos**, o formato de hoje: zero mudança
  em `store.py`. Custa espalhar conhecimento do formato gravado por seis
  classes e colocar o `match` da união dentro de `BankUnit`, que não deveria
  saber que JSON existe. Rejeitado.
- **Biblioteca de serialização** (`pydantic`, `dataclasses-json`,
  `cattrs`): resolveria a união com discriminante de graça. Custa uma
  dependência nova, o que é emenda à constituição, para 8 tipos simples.
  Rejeitado.
- **`dataclasses.asdict()` + reconstrução manual**: `asdict` é recursivo e
  cospe a união sem discriminante, então a volta continuaria manual e a ida
  ficaria com um formato que não é o desenhado. Rejeitado.

---

## D8 — Dois tipos de visão, não um com campos opcionais

**Decisão**: `PlayerSideView` tem `hand: list[CardDocument]`;
`OpponentSideView` tem `hand_size: int` e **não tem** o campo `hand`.

**Rationale**: é o que transforma FR-035 de uma regra que a revisão precisa
pegar em um erro de mypy. Um tipo único com `hand: list[...] | None` deixaria
o vazamento ser um bug de valor — alguém preenche o campo — em vez de um erro
de tipo. Com dois tipos, não existe onde escrever a mão do oponente.

A mesma lógica vale para o deck: **nenhum** dos dois tipos tem campo de
conteúdo de deck, só `deck_size`. FR-034 fala dos dois decks, inclusive o
próprio.

**Alternativas consideradas**:

- **Um `SideView` com campos opcionais**: menos tipos, mas o compilador para
  de ajudar exatamente na fronteira de confiança do jogo. Rejeitado.
- **Filtrar na serialização do websocket**: adia a decisão para a camada de
  transporte, que é onde um esquecimento vira vazamento em produção.
  Rejeitado, e a spec já coloca o envelope fora de escopo.

---

## D9 — O que sobrevive de `models.py`

**Decisão**: o arquivo é apagado, mas três coisas são transplantadas, não
reescritas do zero.

| Do arquivo antigo | Para onde vai | Por quê |
|---|---|---|
| O comentário do `MatchState` sobre chave de objeto JSON ser sempre string | `documents.py`, adaptado | A observação continua verdadeira e é a razão de o formato novo **não** ter chave por `user_id`. Vira o comentário que explica por que a lista de dois foi escolhida. |
| O docstring de `has_player` — "a partida é o dono da regra de quem pode falar com ela" — e o `>>> match.has_player(7)` | `match_state.py`, intacto | Carrega a intenção do gate de participante, que é o único consumidor real do `Match` hoje. |
| O comentário de `Match.__init__` sobre ser construída pelo `MatchStore` e nunca direto de um consumer | `match_state.py`, adaptado a `Match.start` | Registra a razão de a partida existir no Redis: outros workers precisam enxergá-la. |

**Rationale**: a constituição manda preservar comentários num refactor porque
eles carregam intenção e proveniência. Apagar um arquivo não é licença para
descartar a intenção que ele registrava — só para descartar o código que a
implementava mal.

**O que não sobrevive**: `play_card` inteiro (regra no lugar errado, FR-042),
`CardId = str` (o `CardId` do catálogo assume, fechando a pendência do
`Backend/TODO.md`), `board_state` e `hands` (substituídos por zonas dentro de
`PlayerState`), e o `turn` de `user_id` (vira `priority_user_id`, que é o nome
que a §2 usa).

---

## D10 — Estado inicial sem o setup da §3

**Decisão**: `Match.start(player1, player2)` produz rodada 1, fase `UPKEEP`,
Nexus 20 dos dois lados, energias em 0, `token_consumed=False`,
`consecutive_passes=0`, pilha vazia, quatro zonas vazias,
`next_card_instance_id=1`, `token_holder_user_id` e `priority_user_id` iguais
ao `user_id` do primeiro do par.

**Rationale**: é o mínimo que satisfaz FR-040 sem invadir a próxima feature. O
estado é **válido** — todo campo tem valor do tipo certo, e o gate de
participante funciona — mas não é **jogável**, e a spec diz exatamente isso.

O dono do token determinístico é valor de espera, não regra. Fica com um
comentário apontando a §3, para que a feature de setup encontre o ponto em vez
de procurá-lo.

**Alternativas consideradas**:

- **Sortear o token já aqui**: é uma linha de `random.choice`. Rejeitado: o
  sorteio da §3 acontece **depois** do mulligan e determina quem compra a
  quinta carta. Sorteá-lo cedo, num ponto que não faz o resto, é meia regra
  espalhada — e a spec põe a §3 fora de escopo por inteiro.
- **`Match.start` recebendo o deck de cada jogador**: aproximaria do estado
  jogável. Rejeitado: montar deck exige validação (`ensure_valid_deck`), fonte
  do deck do jogador e o embaralhamento da §3 — tudo da próxima feature.

---

## D11 — Nomes

**Decisão**: registrada aqui porque a constituição pede nome específico com
menos de 5 ocorrências no grep, e três nomes deste desenho mereciam nota.

| Nome | Por quê |
|---|---|
| `MatchCard` | Não `Card`, que é o molde do catálogo e já existe; não `CardInPlay`, porque carta no deck não está em jogo. É "carta que pertence a uma partida", que é a definição do FR-009. |
| `BankUnit` | Não `Unit`, que é o molde do catálogo; não `BoardUnit`, porque o vocabulário da §1 é "banco", não "tabuleiro". |
| `MatchDocument` e família | A forma gravada. Não `MatchState`, que o arquivo antigo usava para o `TypedDict` e que agora descreveria melhor o objeto vivo — reaproveitar o nome com significado trocado é a pior opção. `Document` diz "isto é o que vira JSON". |

Identificadores em inglês, comentários e docstrings em português, como o resto
de `apps/game/`. As cinco fases da §2 viram `UPKEEP`, `ACTION`,
`STACK_RESOLUTION`, `COMBAT`, `ROUND_END`, com o nome da nota em comentário.

---

## Riscos

| Risco | Mitigação |
|---|---|
| A ida e volta ser testada só no caminho feliz e deixar passar um campo esquecido | O teste central monta um estado com **todas** as zonas não vazias, dano, modificadores das duas durações e pilha com dois feitiços, e compara o objeto reconstruído inteiro — não campo a campo. `fake_match_state.py` é quem monta esse estado, uma vez, para todos os testes. |
| Um requisito de proibição (FR-011, FR-017, FR-034) passar em teste por engano | Cada um vira teste de inspeção da estrutura serializada, não de comportamento: varrer o JSON e afirmar que a chave não existe. É o que SC-006 e SC-007 pedem. |
| O formato gravado mudar e quebrar partidas vivas no Redis | A spec registra que não há versionamento e que o TTL de 6 horas fecha a janela. Vale só porque não existe produção; o dia em que existir, o campo de versão entra antes. |
