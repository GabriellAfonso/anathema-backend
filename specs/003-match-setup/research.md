# Phase 0 — Pesquisa e decisões de desenho: Setup de Partida

**Feature**: `003-match-setup` | **Data**: 2026-09-10 | **Spec**:
[spec.md](./spec.md)

As três perguntas travadas da spec já foram respondidas em *Clarifications* e
entram aqui só como consequência de desenho. O que esta fase resolve é como
cada resposta vira código sem violar princípio da constituição.

---

## D1 — Onde o setup mora: um pacote `engine/` novo

**Decisão**: `server/apps/game/engine/`, pacote novo, plano, com `__all__`
explícito como `cards/` e `match/`.

**Razão**: `apps/game/match/__init__.py` declara, em letras de forma, que nada
ali é regra: *"não se decide se uma jogada é legal, não se aplica dano, não se
troca prioridade nem se avança fase. O estado é dado; quem o transforma é o
motor."* O setup da §3 embaralha, compra, troca cartas e sorteia o token —
é transformação, é regra, é motor. Colocá-lo dentro de `match/` contradiz o
docstring do próprio pacote na primeira feature que o exercita.

O motor não existia até agora. Esta feature é a primeira peça dele, e o Upkeep
da §4, a compra geral da §9 e o combate da §7 vão para o mesmo pacote. Criá-lo
agora com um módulo por passo é o caminho previsível que a constituição pede
(*Structural rules*), e evita a alternativa pior: o motor nascer espalhado
entre `match/` e os consumers.

**Alternativas descartadas**:

- `match/setup.py`. Mais barato hoje, mas quebra a separação que a feature 002
  gastou uma spec inteira estabelecendo. A próxima feature teria de mover o
  arquivo de qualquer jeito.
- `apps/game/rules/`. Nome igualmente bom, mas o vocabulário do vault já diz
  "motor" (§13: *"É problema de transporte, não de regra — mora no consumer,
  não no motor"*). `engine/` é a tradução direta desse termo.
- Um app Django novo. Sem model, sem migration, sem URL: seria `INSTALLED_APPS`
  a mais por nada.

---

## D2 — A fonte de aleatoriedade: semente na partida, sorteio numerado

**Decisão**: três peças, em `server/apps/game/randomness.py`:

- `RandomSeed = NewType("RandomSeed", str)` — a semente da partida.
- `Roll` — dataclass congelada `(seed, ordinal)`: um sorteio identificado.
- `RandomSource` — `Protocol` com `shuffled(items, roll)` e
  `choose(options, roll)`. A implementação `SeededRandomSource` constrói um
  `random.Random(f"{seed}:{ordinal}")` por chamada.

O `Match` carrega `random_seed` e `next_roll_ordinal`, e cunha sorteios com
`mint_roll()` — o mesmo formato de `mint_card_instance_id()`, que a feature 002
já usa para identidade de carta.

**Razão**: a clarificação exige que o mulligan e o sorteio do token, que
acontecem depois da criação e possivelmente em outro worker, continuem a mesma
sequência. Guardar um objeto gerador no estado é impossível — ele não
serializa. Guardar "quantos números já saíram" e adiantar o gerador na
recarga funciona, mas amarra a reprodutibilidade à quantidade exata de números
que cada operação consome: mudar a implementação do embaralhamento mudaria
partidas antigas, e um `shuffle` de 40 cartas não promete quantos números
consome.

Numerar o sorteio resolve os dois problemas: cada operação recebe um fluxo
próprio, derivado de `(semente, ordinal)`. Quantos números uma operação consome
deixa de importar, porque a próxima operação não continua o mesmo fluxo — ela
abre outro. O que precisa sobreviver ao Redis é um inteiro pequeno.

`random.Random(str)` semeia por SHA-512 do texto, não por `hash()`, então o
resultado não depende de `PYTHONHASHSEED` nem do processo. Semear com uma tupla
não é aceito nas versões atuais; por isso a chave é a string `"semente:ordinal"`
e a semente é `str`, não `int` — e assim ela também atravessa o JSON sem
conversão.

**Alternativas descartadas**:

- **Injetar uma fonte nova a cada chamada, sem semente no estado.** Era a opção
  A da clarificação. Dois workers = dois fluxos, e o setup deixa de ser
  reproduzível a partir do estado gravado.
- **Guardar o estado interno do Mersenne Twister** (`random.getstate()`) no
  documento. Serializa, mas são 625 inteiros por partida no Redis a cada
  gravação, e o formato é detalhe de implementação do CPython — exatamente o
  tipo de coisa que a constituição manda esconder atrás de interface própria,
  não gravar.
- **Contar números consumidos e adiantar na recarga.** Frágil pelo motivo
  acima, e caro: adiantar exige repetir o consumo.

**Nome**: `Roll`, não `Draw`. "Draw" é compra de carta neste domínio
(`draw_from_deck_top`), e dois significados para a mesma palavra dentro do
mesmo pacote é exatamente o que a constituição proíbe ao pedir nomes com menos
de 5 ocorrências no grep. `roll` não aparece hoje em `apps/`.

---

## D3 — A espera do mulligan: um booleano por jogador, "quem falta" derivado

**Decisão**: `PlayerState.mulligan_taken: bool = False`. O `Match` responde
"de quem estou esperando" por uma propriedade derivada,
`awaiting_mulligan_user_ids`, nunca por um campo gravado.

**Razão**: a alternativa — uma lista de `user_id` pendentes dentro do `Match` —
cria uma segunda fonte de verdade que precisa ficar em sincronia com a tupla de
jogadores, e o esquecimento não dá erro: dá espera eterna. É a mesma razão pela
qual `PlayerState.user_id` é propriedade sobre `profile` e não campo próprio,
já registrada no código da feature 002.

Com um booleano por jogador, a serialização é um campo a mais no
`PlayerDocument`, e "quem falta" é uma varredura de dois elementos.

**Consequência**: registrar o mulligan de um jogador **não** precisa mais
guardar a seleção dele. A clarificação decidiu que os passos (a) a (d) executam
na chegada, então as cartas separadas voltam ao deck dentro da mesma operação
e nunca existe um conjunto "de lado" a persistir (FR-030).

---

## D4 — Dono do token e prioridade passam a ser opcionais

**Decisão**: `token_holder_user_id: int | None` e `priority_user_id: int | None`,
os dois `None` até o sorteio, os dois preenchidos juntos por `finish_setup`.

**Razão**: a spec mata explicitamente o valor de espera — o comentário atual
"valor de espera, não regra: quem sorteia o dono do token é a §3" deixa de ser
verdade (FR-051). Durante a espera do mulligan não existe dono do token, e
declarar `token_holder_user_id = players[0]` é afirmar uma coisa falsa que
nenhum teste pega.

`None` é a afirmação honesta, e sob `strict = True` todo leitor é obrigado pelo
mypy a tratar o caso. O custo é real e está contabilizado: `PlayerView` passa a
declarar os dois campos como `int | None`, e o cliente precisa saber desenhar a
tela de mulligan sem dono de token — que é a tela que ele vai ter mesmo.

**Alternativa descartada**: um `MatchPhase.MULLIGAN` que garanta implicitamente
que ninguém lê o dono do token. Garantia por convenção, não por tipo — e o
tipo é gratuito.

---

## D5 — A fase nova: `MULLIGAN`, ao lado das cinco da §2

**Decisão**: `MatchPhase.MULLIGAN = "mulligan"`, sexto valor do `StrEnum`, e
`phase` passa a ter esse valor como padrão do `Match`.

**Razão**: FR-025. O conjunto continua fechado — o que muda é a cardinalidade.
O docstring de `MatchPhase`, que hoje diz "As cinco fases da §2. Conjunto
fechado.", passa a explicar por que existe um valor que a §2 não lista: a §2
descreve o ciclo da rodada, e o setup acontece antes da primeira rodada.

Nenhuma partida volta para `MULLIGAN` depois de sair: é caminho só de ida, e a
spec registra isso em *Assumptions*.

**Alternativa descartada**: um campo `setup_done: bool` separado da fase.
Duas coisas para manter em sincronia, e a pergunta "em que ponto o jogo está?"
passaria a exigir duas leituras.

---

## D6 — Mutação atômica: CAS otimista sobre uma versão, não trava

**Decisão**: a partida passa a ser gravada como um **hash** Redis com dois
campos, `version` e `state`. `MatchStore` ganha:

```
async def mutate(self, match_id: str, change: Callable[[Match], None]) -> Match
```

que lê versão e estado juntos, aplica `change` na cópia local, e grava com um
script Lua que só escreve se a versão no Redis ainda for a que foi lida. Versão
diferente = alguém escreveu no meio; relê e repete, até um teto de tentativas.

**Razão**: o mulligan simultâneo é o primeiro read-modify-write real do projeto
— exatamente o que o docstring de `store.py` registrou como adiado. A
clarificação decidiu resolver agora.

Por que CAS e não Lua puro: a mutação é lógica Python (embaralhar com a fonte
injetada, mover cartas, validar a seleção). Não dá para descê-la para dentro de
um script, como o pareamento da fila fez — aquele é `LREM`/`RPUSH`/`LPOP`, três
comandos Redis; este é o motor de regras.

Por que CAS e não `SET NX` como trava: uma trava tem tempo de vida, e tempo de
vida é uma segunda coisa a acertar — curto demais e dois donos escrevem, longo
demais e uma queda de worker congela a partida. O CAS não tem relógio: ou a
versão bate, ou não bate.

Por que a versão fica num **campo de hash** e não dentro do JSON: comparar
versões dentro do documento obrigaria o script a `cjson.decode` do estado
inteiro a cada escrita, para ler um inteiro. Um `HGET key version` lê o inteiro
direto. O documento não muda de forma, e `documents.py` não sabe que
concorrência existe.

**A retentativa é segura** porque `change` é reaplicado sobre uma leitura
fresca: o ordinal do sorteio vem da partida recarregada, então a tentativa que
vence usa um ordinal que ninguém usou. Uma recusa levantada de dentro de
`change` aborta sem escrever nada, que é o FR-023.

**Não confundir com o versionamento que a feature 002 dispensou.** Aquele era
versão de **esquema** (que formato o documento tem), e continua não existindo.
Este é versão de **escrita** (quantas vezes esta partida mudou), e serve só ao
CAS. O comentário no código precisa dizer isso, ou alguém junta os dois.

**Alternativas descartadas**:

- `WATCH`/`MULTI`/`EXEC` do próprio Redis. Faz a mesma coisa, mas `WATCH` é por
  conexão, e a `Redis` do redis-py é um pool: garantir que o `WATCH` e o `EXEC`
  saem da mesma conexão exige tomar a conexão na mão. Um script registrado não
  tem esse problema.
- Trava distribuída (Redlock ou `SET NX PX` simples). Ver acima.

---

## D7 — O movimento de compra fica em um lugar só

**Decisão**: `engine/card_draw.py::draw_from_deck_top(player) -> MatchCard`.
Tira `deck[0]` e põe no fim da mão. Levanta se o deck estiver vazio, com o
`user_id` na mensagem.

**Razão**: FR-014. O setup compra 4 + 1, o mulligan compra a reposição, e a §9
vai comprar no Upkeep — quatro chamadores para o mesmo movimento. A §9
acrescenta duas condições em volta (teto de mão, reset de deck), e é isso que
a próxima feature escreve: uma função que checa e delega, não uma segunda cópia
do movimento.

Levantar com deck vazio é a escolha certa **aqui** porque durante o setup é
impossível — 40 cartas, 5 compras — e portanto seria bug. A §9 vai chamar
depois de já ter feito o reset de deck, então também nunca vê deck vazio.

**Onde o topo do deck fica**: `deck[0]`, como o comentário de
`player_state.py` já fixou (*"Topo do deck é o começo da lista"*). Não mudar
isso agora; o custo de `pop(0)` numa lista de 40 é irrelevante.

---

## D8 — `Match.start` morre; o store deixa de criar partida

**Decisão**: `Match.start` é removido. `MatchStore.create` também. O caminho
passa a ser: `start_match(...)` no engine devolve um `Match`, e quem quiser
persistir chama `store.save(match)`.

**Razão**: com dois decks, um catálogo, uma fonte de aleatoriedade e uma
semente, um `create` no store teria seis parâmetros e faria validação de deck
dentro da camada de armazenamento. `store.py` diz de si mesmo que é
armazenamento; criar partida virou regra na hora em que virou §3.

`MatchStore` fica com `get`, `save` e `mutate` — três operações, todas sobre
bytes. `FakeMatchStore` acompanha (FR-050).

**Assinatura de `start_match`**: os dois lados chegam como `MatchEntry`, uma
dataclass congelada de `(profile, deck)`, em vez de quatro parâmetros
posicionais pareados. Trocar `player1`/`deck1` por engano deixa de ser
possível quando os dois viajam juntos.

---

## D9 — O deck de andaime do matchmaking

**Decisão**: `cards/starter_deck.py::starter_deck(catalog) -> Deck`. Monta 40
identificadores válidos a partir do catálogo recebido: 3 cópias das primeiras
13 cartas ordenadas por `card_id`, mais 1 da décima quarta.

**Razão**: a spec registra em *Assumptions* que a origem real do deck é outra
feature, e que até lá o matchmaking fornece um deck determinístico. Ele precisa
existir em algum lugar, e `cards/` é quem já é dono de `Deck` e de
`deck_rules.py`.

Deriva do catálogo injetado em vez de listar 40 números à mão: assim o teste
prova que o andaime passa em `deck_problems()` sem precisar ser atualizado toda
vez que o catálogo mudar.

O docstring diz que é andaime e cita a feature que vai substituí-lo, para não
virar contrato por descuido.

**Alternativa descartada**: o consumer montar a lista inline. Vira 40 números
soltos no meio de código de websocket, sem teste próprio.

---

## D10 — Recusas: uma exceção por pergunta, cada uma nomeando o valor

**Decisão**:

| Recusa | Exceção | Mora em |
|---|---|---|
| Deck inválido de um dos lados | `InvalidPlayerDeckError(user_id, problems)` | `engine/match_setup.py` |
| Mulligan de quem não joga | `NotAParticipantError` — **reusada** | `match/match_state.py` |
| Mulligan repetido, ou fora da janela | `MulliganAlreadyTakenError(user_id, match_id)` | `engine/mulligan.py` |
| Carta que não está na mão, ou repetida na seleção | `CardNotInHandError(card_instance_id, user_id)` | `engine/mulligan.py` |

**Razão**: `InvalidPlayerDeckError` **envolve**, não substitui,
`deck_problems()` da feature 001 — a validação é reaproveitada, e o que a
camada nova acrescenta é de quem era o deck (FR-003, FR-005). A mensagem
concatena os problemas do jeito que `InvalidDeckError` já concatena.

`NotAParticipantError` já existe e já cita o `user_id` e o `match_id`:
`match.player(user_id)` a levanta sozinha, então FR-020 sai de graça no
caminho normal.

Mulligan fora da janela não ganha exceção própria: quando o setup termina, os
dois jogadores estão com `mulligan_taken = True`, então a segunda tentativa e a
tentativa tardia caem no mesmo lugar — que é o que a spec pede em *Edge Cases*.

Carta repetida na seleção também não ganha exceção própria: a validação
consome a mão candidata removendo o que já casou, então a segunda ocorrência
do mesmo identificador simplesmente não está mais lá (FR-022).

**FR-023 — recusa não altera nada**: a validação da seleção inteira acontece
antes de qualquer mutação. `record_mulligan` resolve os identificadores em
cartas primeiro; só depois tira da mão.

---

## D11 — Fakes nomeados que esta feature precisa

**Decisão**: dois arquivos novos em `apps/game/tests/`, no formato dos que já
existem.

- `fake_random_source.py` — `ScriptedRandomSource`, com a mesma superfície de
  `RandomSource`: `shuffled` devolve a ordem que o teste ditou (por padrão, a
  lista invertida) e `choose` devolve o índice que o teste fixou. Leva a mesma
  asserção estática de conformidade de `Protocol` que `fake_card_catalog.py`
  carrega — e pelo mesmo motivo, que aquele arquivo já explica em um comentário
  que manda não apagar.
- `fake_setup.py` — partidas já passadas pelo setup, para os testes que
  precisam de uma partida jogável sem repetir a montagem.

`fake_match_state.py` continua sendo fake de **estado** e passa a construir o
`Match` diretamente, já que `Match.start` deixa de existir. Não vira fake de
engine: montar zona na mão é o que ele existe para fazer.

**Razão**: constituição, princípio V — fake nomeado, nunca stub inline. A fonte
de aleatoriedade é a peça mais injetada desta feature; um `lambda` no meio de
cada teste seria a violação mais provável.

---

## D12 — O consumer de mulligan não entra

**Decisão**: nenhum `handle_mulligan` em `MatchConsumer`. Esta feature entrega
`record_mulligan` e `MatchStore.mutate`; quem os liga a uma mensagem de
websocket é a feature de transporte.

**Razão**: a spec põe envelope, broadcast e reconexão em *Out of Scope*, com a
frase "esta feature define o que a decisão de mulligan significa, não como ela
viaja". O roteamento de `base.py` já resolve `handle_<type>` por `getattr`,
então o handler é uma função de poucas linhas quando chegar a hora — não vale
antecipar.

Vale registrar o já conhecido: `consumers/base.py:155` roteia `play_card` para
um handler que ninguém implementa. O plano da feature 002 já registrou isso
como fora de escopo e continua fora.
