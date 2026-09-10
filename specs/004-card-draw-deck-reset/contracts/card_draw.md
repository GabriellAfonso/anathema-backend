# Contrato — a superfície pública da compra

**Feature**: `004-card-draw-deck-reset` | **Data**: 2026-09-10

Duas superfícies: `apps.game.engine.card_draw` (reescrito) e
`apps.game.engine.deck_reset` (novo), os dois reexportados por
`apps.game.engine`. Assinaturas são o contrato; corpos são da implementação.

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport` — sem a lista, ninguém importa do pacote.

---

## 1. `apps.game.engine.card_draw`

```python
# Fluxo de Partida §12. Aplicado aqui porque aplicá-lo é regra, e a §9 é a
# única regra que o aplica -- `player_state.py` diz isso no próprio docstring.
MAX_HAND_SIZE = 10


class NegativeDrawCountError(Exception):
    """Pediram uma quantidade negativa de compras, citando o valor.

    Comprar 0 é válido (o mulligan de 0 cartas repõe 0). Negativo é conta
    errada de quem chamou -- um `len(...) - 1` que passou do zero -- e sem esta
    recusa passaria como "comprei 0", porque `range(-3)` é vazio.
    """

    def __init__(self, count: int) -> None: ...

    count: int


def draw_card(
    match: Match, user_id: int, *, randomness: RandomSource
) -> MatchCard | None:
    """A §9 inteira: guarda de mão, reset de deck, e então a compra.

    Devolve a carta que entrou na mão, ou `None` quando a compra **não
    aconteceu**. `None` não é erro nem recusa: é a resposta do jogo para a mão
    cheia, e quem chamou segue normalmente. O Upkeep da §4 não trata exceção.

    A ordem das três perguntas é a regra. A guarda de mão vem antes do reset:
    um jogador com 10 cartas na mão e o deck vazio não reseta -- o cemitério
    dele fica onde está.

    Consome um sorteio da partida se, e só se, um reset acontecer.

    >>> draw_card(match, 7, randomness=source).card_id
    15
    >>> draw_card(match, 7, randomness=source) is None   # mão em 10
    True
    """


def draw_cards(
    match: Match, user_id: int, count: int, *, randomness: RandomSource
) -> list[MatchCard]:
    """`count` compras, cada uma passando pelas guardas na sua vez.

    Devolve as cartas que efetivamente entraram na mão, na ordem em que
    entraram -- `len()` é quantas foram. Comprar 3 com 8 na mão devolve 2
    cartas e deixa a mão em 10, nunca em 11.

    Para na primeira compra que não acontece: os dois motivos para `None` --
    mão cheia, e nada de onde comprar -- não se desfazem sozinhos no meio de um
    laço.

    `count == 0` é válido e não muda nada. Negativo levanta.

    >>> len(draw_cards(match, 7, 4, randomness=source))
    4
    """
```

**Não exportado**: o movimento cru. `_take_from_deck_top(player)` é privado do
módulo desde esta feature, para que a §9 seja a única porta (FR-001, FR-031).

**Removido**: `draw_from_deck_top` e `EmptyDeckError`, que a feature 003
exportava. O caminho até a exceção deixou de existir — a razão está em
[research.md](../research.md) D2.

### Recusas

| Situação | Resposta |
|---|---|
| `user_id` que não joga esta partida | `NotAParticipantError` (de `match/`, já existe) |
| `count` negativo | `NegativeDrawCountError` citando o valor |
| mão em 10 | `None` / `[]` — **não é recusa** |
| deck e cemitério vazios | `None` / `[]` — **não é recusa** |

---

## 2. `apps.game.engine.deck_reset`

```python
def reset_deck_from_graveyard(
    player: PlayerState, *, randomness: RandomSource, roll: Roll
) -> None:
    """Todo o cemitério vira o deck, embaralhado. Mão e banco não são tocados.

    Não decide se o reset deve acontecer -- quem decide é a §9, em
    `card_draw.py`. Assume as duas pré-condições que ela já verificou: o deck
    está vazio e o cemitério não.

    Recebe o `Roll` já cunhado em vez de cunhar o seu para que o contador de
    sorteios da partida não avance quando a regra descobre que não há
    cemitério para resetar.

    As cartas voltam com a identidade que já tinham. O reset não cunha
    identidade nova (§9, e `Match.mint_card_instance_id` diz o mesmo).

    >>> reset_deck_from_graveyard(player, randomness=source, roll=match.mint_roll())
    >>> player.graveyard
    []
    """
```

Sem exceções próprias. Chamada com as pré-condições violadas, a função produz
um deck vazio ou descarta um deck com cartas — as duas coisas são bug do
chamador, e a função é privada ao pacote na prática: o único call site é
`card_draw.py`.

---

## 3. `apps.game.engine.__all__`

```python
__all__ = [
    # Compra (§9)
    "draw_card",
    "draw_cards",
    "MAX_HAND_SIZE",
    "NegativeDrawCountError",
    # Reset de deck (§9)
    "reset_deck_from_graveyard",
    # Setup (§3)
    "MatchEntry",
    "start_match",
    "finish_setup",
    "InvalidPlayerDeckError",
    # Mulligan (§3)
    "record_mulligan",
    "MulliganAlreadyTakenError",
    "CardNotInHandError",
]
```

Saem da lista: `draw_from_deck_top` e `EmptyDeckError`.

---

## 4. Os call sites que migram

Três, todos dentro do próprio `engine/`. Nenhum consumer, nenhum arquivo de
`match/`, nenhum arquivo de teste da feature 003.

| Onde | Antes | Depois |
|---|---|---|
| `match_setup._deal_opening_hand` | `for _ in range(4): draw_from_deck_top(player)` | `draw_cards(match, player.user_id, OPENING_HAND_SIZE, randomness=randomness)` |
| `match_setup.finish_setup` | `draw_from_deck_top(match.opponent_of(holder.user_id))` | `draw_card(match, match.opponent_of(holder.user_id).user_id, randomness=randomness)` |
| `mulligan._swap_returned_cards` | `for _ in returned: draw_from_deck_top(player)` | `draw_cards(match, player.user_id, len(returned), randomness=randomness)` |

Nenhum dos três precisa olhar o retorno: as guardas não disparam no setup (mão
parte de zero, deck tem 40), e é isso que faz o comportamento observável não
mudar (FR-030, SC-008).

`_deal_opening_hand` já recebe `match` e `randomness`. `_swap_returned_cards`
também. Nenhuma assinatura interna do setup precisa crescer.
