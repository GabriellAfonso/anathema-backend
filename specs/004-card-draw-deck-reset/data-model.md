# Data Model — Compra de Carta e Reset de Deck

**Feature**: `004-card-draw-deck-reset` | **Data**: 2026-09-10

Esta feature **não cria estado**. Nenhum campo novo, nenhuma mudança em
`documents.py` ou `serialization.py`, nenhuma migration. O que segue é o que
ela lê, o que ela escreve, e os invariantes que precisam valer depois de cada
operação.

Assinaturas estão em [contracts/card_draw.md](./contracts/card_draw.md).

---

## 1. O que a operação toca

De `PlayerState` (feature 002), de um jogador só:

| Campo | Leitura | Escrita |
|---|---|---|
| `hand: list[MatchCard]` | tamanho, para a guarda | a carta comprada é anexada ao fim |
| `deck: list[MatchCard]` | vazio ou não; `deck[0]` é o topo | perde o topo na compra; é substituído inteiro no reset |
| `graveyard: list[MatchCard]` | vazio ou não | esvaziado no reset |
| `bank: list[BankUnit]` | — | — |
| `nexus`, `energy_max`, `energy_current` | — | — |
| `profile`, `mulligan_taken` | — | — |

De `Match` (feature 002):

| Campo/método | Uso |
|---|---|
| `player(user_id)` | resolve o jogador; recusa `user_id` de fora |
| `mint_roll()` | cunha o sorteio do reset — **só quando o reset acontece** |
| `next_roll_ordinal` | avança dentro de `mint_roll()`, e só ali |
| `next_card_instance_id` | **nunca** avança nesta feature |

O oponente não é lido nem escrito em nenhum caminho.

---

## 2. A tabela da §9

As três entradas da regra, mais o quarto caso que a spec fechou. A ordem das
colunas é a ordem em que a regra pergunta.

| Mão | Deck | Cemitério | O que acontece | Devolve |
|---|---|---|---|---|
| ≥ 10 | qualquer | qualquer | nada | `None` |
| < 10 | tem carta | qualquer | move `deck[0]` para o fim da mão | a carta |
| < 10 | vazio | tem carta | reset, depois move `deck[0]` | a carta |
| < 10 | vazio | vazio | nada | `None` |

A segunda coluna só é olhada depois de a primeira ter passado. É isso que
FR-003 fixa: um jogador com a mão em 10 e o deck vazio **não reseta** — o
cemitério dele fica onde está.

A quarta linha é defensiva. Em partida legal ela é inalcançável; a conta está
na seção Clarifications de [spec.md](./spec.md).

---

## 3. Invariantes

Depois de **qualquer** chamada de `draw_card` ou `draw_cards`:

- **I1 — Conservação.** O multiconjunto de `card_instance_id` em
  `deck ∪ hand ∪ bank ∪ graveyard` do jogador é idêntico ao de antes. Nenhuma
  carta nasce, some ou duplica.
- **I2 — Identidade estável.** `match.next_card_instance_id` não mudou. Nenhum
  caminho desta feature cunha identidade (FR-019).
- **I3 — Cemitério só encolhe.** `graveyard` ou continua idêntico, ou fica
  vazio. Nunca ganha carta (FR-017).
- **I4 — Banco e vitais intactos.** `bank`, `nexus`, `energy_max` e
  `energy_current` são idênticos aos de antes (FR-012).
- **I5 — Oponente intacto.** O `PlayerState` do outro jogador é idêntico ao de
  antes (FR-004).
- **I6 — Teto respeitado.** `len(hand) <= 10` (FR-005).
- **I7 — Sorteio só com reset.** `match.next_roll_ordinal` avançou exatamente
  uma vez por reset ocorrido, e nenhuma vez se nenhum reset ocorreu (FR-024).

Depois de uma chamada que devolveu `None` (ou uma lista mais curta que `count`),
vale um invariante mais forte para a compra que não aconteceu:

- **I8 — No-op é no-op.** Nenhuma das quatro zonas mudou, em conteúdo ou em
  ordem, e `next_roll_ordinal` não avançou (FR-006, FR-034).

---

## 4. As duas transições

### 4.1 Compra (`_take_from_deck_top`)

```
antes:  deck = [c0, c1, ..., cn]   hand = [h0, ..., hm]
depois: deck = [c1, ..., cn]       hand = [h0, ..., hm, c0]
```

`c0` é o mesmo objeto, com o mesmo `card_instance_id` e o mesmo `card_id`
(FR-020). Nada é copiado, nada é recriado.

Pré-condição, garantida pelo único chamador: `deck` não está vazio.

### 4.2 Reset (`reset_deck_from_graveyard`)

```
antes:  deck = []                  graveyard = [g0, ..., gk]
depois: deck = shuffled([g0..gk])  graveyard = []
```

O deck novo é uma permutação exata do cemitério (FR-016), produzida por
`randomness.shuffled(...)` com o `Roll` que o chamador cunhou. `shuffled`
devolve lista nova e não toca a original, então esvaziar o cemitério depois é
seguro.

As cartas são os mesmos objetos. Uma unidade que morreu chega ao cemitério como
`MatchCard` — o `BankUnit` que carregava dano e modificadores ficou para trás
na §7.4, por construção do modelo da feature 002 — então nada precisa ser
zerado aqui (FR-018).

Pré-condições, garantidas pelo único chamador: `deck` está vazio e `graveyard`
não está.

---

## 5. Compra múltipla

`draw_cards(match, user_id, count, ...)` é `draw_card` chamado até `count`
vezes, parando no primeiro `None`. Não tem estado próprio e não conhece as
guardas.

| Entrada | Resultado |
|---|---|
| `count == 0` | `[]`, nada muda (FR-028) |
| `count < 0` | `NegativeDrawCountError` citando o valor |
| mão em 8, `count == 3`, deck cheio | 2 cartas; mão fica em 10 (FR-026) |
| mão em 10, `count == 3` | `[]`, nada muda |
| mão em 2, deck com 1, cemitério com 3, `count == 3` | 3 cartas; um reset no meio |

`len(resultado)` é a contagem que FR-027 pede.

---

## 6. Constante

| Nome | Valor | Onde | Fonte |
|---|---|---|---|
| `MAX_HAND_SIZE` | 10 | `engine/card_draw.py` | Fluxo de Partida §12 |

Mora com quem a aplica, como `DECK_SIZE` em `cards/deck_rules.py` e
`STARTING_NEXUS` em `match/player_state.py`. A razão está em
[research.md](./research.md) D6.

---

## 7. Round-trip

Nenhum campo novo, então a garantia da feature 002 vale por construção. O teste
existe assim mesmo (FR-032) porque o estado logo depois de um reset tem uma
forma que nenhum fake atual produz: cemitério vazio, deck reordenado por um
sorteio de meio de partida, e `next_roll_ordinal` acima de 1.

O que precisa voltar igual: ordem do deck novo, cemitério vazio, mãos,
`next_card_instance_id` e `next_roll_ordinal`.
