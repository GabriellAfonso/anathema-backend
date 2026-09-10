# Research — Compra de Carta e Reset de Deck

**Feature**: `004-card-draw-deck-reset` | **Data**: 2026-09-10

Fase 0. Cada decisão registra o que foi escolhido, por quê, e o que foi
descartado. Nenhum NEEDS CLARIFICATION restou da spec — a única pergunta aberta
foi respondida na sessão de esclarecimento e está na seção Clarifications de
[spec.md](./spec.md).

---

## D1 — A regra da §9 mora no `engine/`, e o movimento cru deixa de ser público

**Decisão**: `apps/game/engine/card_draw.py` deixa de expor
`draw_from_deck_top` e passa a expor a regra inteira da §9: `draw_card` e
`draw_cards`. O movimento vira uma função privada do módulo,
`_take_from_deck_top`.

**Rationale**: FR-001 pede uma porta só, e FR-031 pede o movimento escrito uma
vez só. Manter as duas funções públicas lado a lado deixa a porta dos fundos
aberta: um chamador futuro que importe `draw_from_deck_top` pula as duas
guardas em silêncio, e nenhum teste pega. O próprio docstring que a feature 003
escreveu para o módulo já previa este momento — *"a regra geral que a §9 pede
vai ser uma função que checa as duas e delega aqui, em vez de uma segunda cópia
do movimento"*. A delegação continua; o que muda é que o delegado deixa de ter
nome público.

**Alternativas descartadas**:

- *Manter `draw_from_deck_top` público e só somar `draw_card` por cima.* Duas
  portas, e a errada é a mais curta de digitar.
- *Módulo novo para a regra, deixando `card_draw.py` como está.* Espalha a
  compra por dois arquivos sem separar responsabilidade nenhuma: os dois teriam
  a mesma, "compra".

---

## D2 — `EmptyDeckError` é apagada, não escondida

**Decisão**: a exceção sai do código e do `__all__` do pacote.

**Rationale**: ela existia para o caso "chamaram a compra com o deck vazio",
que era bug de chamador enquanto a §9 não existia. Com a regra no lugar,
`_take_from_deck_top` só é alcançado depois de a regra ter provado que o deck
tem carta — o único caminho até ela passa pela verificação. Manter a exceção
seria manter um braço provadamente inalcançável, e código morto é pior que
código ausente: ninguém consegue distinguir, seis meses depois, uma guarda
inútil de uma guarda que ainda protege alguma coisa.

A intenção que o docstring dela carregava — *por que* comprar de deck vazio não
é fluxo de jogo — não se perde: ela migra para o docstring de `draw_card`, onde
passa a explicar o contrário, que agora **é** fluxo de jogo e tem resposta.

**Alternativas descartadas**:

- *Manter a exceção como asserção interna.* Braço inalcançável com nome
  público, que é o pior dos dois mundos.
- *Trocar por `assert`.* `assert` some com `-O` e o projeto não usa esse estilo
  em lugar nenhum.

**Consequência para os testes**: `test_card_draw.py` perde
`test_an_empty_deck_is_refused_naming_the_owner` e ganha, no lugar, o teste do
deck vazio com cemitério vazio (FR-033). É a mesma pergunta com a resposta que
a §9 agora dá.

---

## D3 — A assinatura recebe `Match` e `user_id`, não `PlayerState`

**Decisão**:

```python
def draw_card(match: Match, user_id: int, *, randomness: RandomSource) -> MatchCard | None
def draw_cards(match: Match, user_id: int, count: int, *, randomness: RandomSource) -> list[MatchCard]
```

**Rationale**: a compra precisa do `Match`, não só do jogador — o sorteio que
embaralha o deck resetado sai de `match.mint_roll()`, e o contador de sorteios
mora na partida (FR-022). Dado que o `Match` já vai junto, receber **também**
um `PlayerState` abriria a porta para o par errado: um `PlayerState` de outra
partida, ou o do oponente por engano. Com `user_id`, o `match.player(user_id)`
que já existe resolve o jogador e recusa um `user_id` de fora nomeando-o.

É a mesma razão pela qual a feature 003 criou `MatchEntry`: perfil e deck
viajam juntos para não poderem ser trocados de par.

**Alternativas descartadas**:

- *`draw_card(player, *, randomness, roll)`, com o sorteio cunhado pelo
  chamador.* Obrigaria a cunhar um sorteio antes de saber se o reset vai
  acontecer, e FR-024 diz que uma compra sem reset não consome aleatoriedade.
  O chamador não tem como saber sem reimplementar a regra.
- *`draw_card(match, player, *, randomness)`.* Redundante e destrancado: nada
  no tipo impede passar o `PlayerState` de outra partida.

---

## D4 — O resultado é `MatchCard | None`, e `None` não é erro

**Decisão**: `draw_card` devolve a carta comprada, ou `None` quando a compra
não aconteceu. `draw_cards` devolve a lista do que efetivamente entrou na mão —
`len()` é a contagem que FR-027 pede.

**Rationale**: FR-007 é explícito em que a mão cheia não é erro nem recusa, e
FR-008 pede que quem chamou saiba se a compra aconteceu. `None` responde as
duas coisas sem obrigar ninguém a `try`. O precedente está no próprio projeto:
`Match.bank_unit()` devolve `None` para o alvo que sumiu, e o docstring dela
explica exatamente esta distinção — *"pedir um jogador que não joga é bug;
perguntar por um alvo que sumiu é o caso normal"*. Comprar com a mão cheia é o
caso normal.

Sob `strict`, `MatchCard | None` obriga todo leitor a tratar o `None` — o mypy
cobra o que a revisão teria de cobrar à mão.

**Alternativas descartadas**:

- *`DrawOutcome(card: MatchCard | None, drawn: bool)`.* `drawn` é derivável de
  `card is not None`; dois campos que podem divergir para dizer uma coisa só.
- *`bool` puro.* Perde a carta, e o Upkeep vai querer avisar o cliente qual
  carta entrou.
- *Levantar exceção com a mão cheia.* Quebraria o Upkeep em toda partida longa,
  que é justamente o que FR-007 proíbe.
- *`draw_cards` devolvendo `int`.* Descarta as cartas de graça; a lista dá a
  contagem e mais.

---

## D5 — O reset é módulo próprio, e não decide nada

**Decisão**: `apps/game/engine/deck_reset.py`, com uma função:

```python
def reset_deck_from_graveyard(
    player: PlayerState, *, randomness: RandomSource, roll: Roll
) -> None
```

Quem decide *se* o reset acontece é `card_draw.py`. Quem o executa é este
módulo, e ele assume que já foi decidido.

**Rationale**: um módulo, uma responsabilidade. "Decidir pela §9" e "mover o
cemitério para o deck embaralhado" são duas, e separá-las mantém os dois
arquivos pequenos e cada um testável sozinho — o de reset sem montar a regra em
volta, o da regra sem provar embaralhamento de novo.

O `Roll` chega por parâmetro em vez de o módulo cunhar o seu: cunhar ali
obrigaria a passar o `Match` inteiro e faria a função consumir o contador antes
de a regra ter certeza de que o reset vai acontecer (FR-034). Com o sorteio de
fora, a função não tem decisão nenhuma para tomar.

**Alternativas descartadas**:

- *Uma função privada dentro de `card_draw.py`.* Junta duas responsabilidades e
  deixa o reset sem teste próprio a não ser através da compra.
- *Método em `PlayerState`.* `match/` declara no próprio docstring que nada ali
  é regra. Reset é regra.

---

## D6 — `MAX_HAND_SIZE` mora com quem a aplica

**Decisão**: `MAX_HAND_SIZE = 10` em `engine/card_draw.py`, exportado pelo
`engine/__init__.py`.

**Rationale**: é o padrão que o projeto já segue para as constantes da §12 —
cada uma mora com a regra que a usa, não num módulo de constantes. `DECK_SIZE`
e `MAX_COPIES_PER_CARD` estão em `cards/deck_rules.py`, `STARTING_NEXUS` em
`match/player_state.py`, `OPENING_HAND_SIZE` em `engine/match_setup.py`.

O docstring de `player_state.py` já aponta para cá: *"Os tetos de mão (10) e de
banco (6) da §12 **não** são validados aqui. Aplicá-los é regra — o de mão
acontece na compra (§9)"*. Pôr a constante em `player_state.py` contradiria a
frase que o próprio arquivo escreveu.

Isto emenda a suposição original da spec, que falava em "constantes de tamanho
de zona" juntas. Esse agrupamento não existe no projeto, e criá-lo agora seria
inventar um módulo para uma constante só.

**Alternativas descartadas**:

- *`apps/game/constants.py` com a §12 inteira.* Um módulo que todo mundo
  importa e ninguém possui; e obrigaria a mover `DECK_SIZE` e `STARTING_NEXUS`
  para lá, mexendo em duas features fechadas por arrumação.
- *Repetir o `10` no ponto de uso.* FR-009 proíbe.

---

## D7 — Compra múltipla é laço sobre a compra única, e para sozinha

**Decisão**: `draw_cards` chama `draw_card` `count` vezes e para no primeiro
`None`, acumulando o que entrou.

**Rationale**: FR-025 exige que cada carta passe pelas guardas na sua vez, e é
exatamente isso que o laço faz. Parar no primeiro `None` não é otimização: é a
regra. Se a mão encheu, ela não desenche no meio do laço; se deck e cemitério
estão os dois vazios, também não. Os dois casos que devolvem `None` são
estáveis dentro de uma compra múltipla, então continuar o laço só gastaria
chamadas para receber `None` de novo.

O contraexemplo que FR-026 nomeia — comprar 3 com 8 na mão dá 10, não 11 — é o
teste que separa esta implementação de uma que verifique a guarda uma vez só,
antes do laço.

**Alternativas descartadas**:

- *Checar a guarda antes do laço e comprar `min(count, 10 - len(hand))`.*
  Duplica a regra, e erra quando um reset falha no meio.
- *Não parar, chamar as `count` vezes.* Mesmo resultado observável, com
  chamadas inúteis — e esconde que a parada é regra, não desempenho.

---

## D8 — Contagem negativa é bug de chamador, e é recusada

**Decisão**: `draw_cards` com `count` negativo levanta `NegativeDrawCountError`,
citando o valor e a forma esperada.

**Rationale**: `range(-3)` é vazio, então sem a guarda um `count` negativo
vindo de uma subtração errada — `len(returned) - 1`, um índice trocado —
passaria como "comprei 0" e ninguém veria. FR-028 diz que 0 é válido; nada diz
que -3 é, e ele quase certamente é o sintoma de uma conta errada acima. A
constituição pede que a mensagem cite o valor ofensor e a forma esperada, e o
projeto já tem o padrão em `EmptyOptionsError` e `InvalidPlayerDeckError`.

**Alternativas descartadas**:

- *Silenciosamente tratar como 0.* Transforma um bug de conta em um resultado
  plausível.
- *`assert count >= 0`.* Some com `-O`, e o projeto não usa `assert` em código
  de produção.

---

## D9 — Os chamadores do setup migram, e os testes do setup não são tocados

**Decisão**: `match_setup.py` e `mulligan.py` trocam `draw_from_deck_top(player)`
por `draw_cards`/`draw_card`. Nenhum arquivo de teste da feature 003 —
`test_match_setup.py`, `test_mulligan.py`, `test_setup_randomness.py` — é
editado.

**Rationale**: é o critério SC-008, e ele é a prova de FR-030. Se o
comportamento observável do setup não mudou, a suíte dele passa sem uma linha
alterada; se alguém precisar mexer nela, o comportamento mudou e a feature
falhou.

As guardas provadamente não disparam no setup: a mão parte de zero e o deck tem
40, então as 4 compras iniciais, a compensação e a reposição do mulligan (no
máximo 4) nunca chegam a 10 na mão nem zeram o deck. E FR-024 garante que
nenhuma dessas compras consome sorteio, então os ordinais que o setup gasta —
e que `test_setup_randomness.py` afirma — continuam os mesmos.

`test_card_draw.py` **é** editado, e não contradiz o critério: ele é o teste da
compra, que é o que esta feature reescreve, não um teste do setup.

**Alternativas descartadas**:

- *Deixar o setup no movimento cru e só usar a regra nova no Upkeep.* Mantém
  duas portas, contra FR-001 e FR-031, e deixa a migração para uma feature que
  vai ter outra coisa para fazer.

---

## D10 — O round-trip depois do reset tem teste próprio, sem campo novo

**Decisão**: nenhuma mudança em `documents.py`, `serialization.py` ou
`store.py`. O teste de FR-032 mora em `test_deck_reset.py` e usa
`to_match_document` / `match_from_document` diretamente.

**Rationale**: o reset não cria estado — ele move cartas entre duas listas que
a feature 002 já serializa e reordena uma delas. A garantia de round-trip vale
por construção. O teste existe mesmo assim porque a spec pede (FR-032) e porque
o estado logo depois de um reset tem uma forma que nenhum fake atual produz:
cemitério vazio e deck reordenado por um sorteio de meio de partida.

Fazer o teste sem Redis é de propósito: a serialização é onde o round-trip pode
quebrar, e o Redis é só o meio. Os testes de store que usam o banco 15 continuam
sendo os da feature 003, e esta feature não acrescenta I/O nenhum.

**Alternativas descartadas**:

- *Somar o caso ao `test_match_serialization.py`.* Espalharia a prova desta
  feature num arquivo de outra, e é o arquivo que menos deve mudar por causa de
  regra.
- *Testar contra o Redis de verdade.* Lento, e não prova nada que a
  serialização já não prove.

---

## D11 — Determinismo do reset se prova com as duas fontes, não com uma

**Decisão**: `test_deck_reset.py` usa `ScriptedRandomSource` para afirmar a
ordem exata do deck resetado, e `SeededRandomSource` com semente fixa para
afirmar a repetibilidade (FR-023, SC-005).

**Rationale**: é a divisão que `fake_random_source.py` já documenta no próprio
docstring — *"Quem quer provar determinismo de verdade usa `SeededRandomSource`
com uma semente fixa"*. Um teste que afirmasse ordem concreta com a fonte
semeada estaria afirmando o algoritmo do CPython; um que afirmasse determinismo
com a fonte roteirizada não estaria afirmando nada, porque ela é determinística
por construção.

O caso da recarga (US5, cenário 5) também não precisa de Redis: serializar,
desserializar e provocar o segundo reset prova que a sequência continua de onde
parou, porque é o `next_roll_ordinal` gravado que a sustenta.

**Alternativas descartadas**:

- *Só a fonte roteirizada.* Não prova FR-023.
- *Só a fonte semeada.* Nenhum teste consegue afirmar qual carta ficou no topo
  sem depender do gerador do CPython.

---

## Resumo das decisões

| # | Decisão | FRs cobertos |
|---|---|---|
| D1 | A regra no `card_draw.py`; movimento privado | FR-001, FR-031 |
| D2 | `EmptyDeckError` apagada | FR-031, FR-033 |
| D3 | Assinatura com `Match` + `user_id` | FR-004, FR-022 |
| D4 | `MatchCard \| None` como resultado | FR-007, FR-008, FR-027 |
| D5 | `deck_reset.py` separado, sem decisão | FR-010 a FR-016 |
| D6 | `MAX_HAND_SIZE` em `card_draw.py` | FR-005, FR-009 |
| D7 | Compra múltipla é laço, e para sozinha | FR-025, FR-026 |
| D8 | `count` negativo é recusado | FR-028 |
| D9 | Setup migra; testes do setup intocados | FR-029, FR-030 |
| D10 | Round-trip sem campo novo, sem Redis | FR-032 |
| D11 | Duas fontes de aleatoriedade nos testes | FR-021, FR-023 |
