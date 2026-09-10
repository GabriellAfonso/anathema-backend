"""A compra de carta da §9: a única porta pela qual uma carta sai do deck e
entra na mão.

Toda compra do jogo passa por aqui -- as 4 do setup, a reposição do mulligan, a
carta de compensação de quem não recebeu o token, o 1 do Upkeep quando a §4
entrar, e qualquer feitiço futuro que mande comprar.

A regra tem três passos, e a ordem entre eles é parte dela:

    1. mão com 10 cartas -> não compra
    2. deck vazio -> reset de deck, e só então compra
    3. caso contrário -> a carta do topo do deck vai para a mão

A guarda de mão vem antes do reset. Um jogador com 10 na mão e o deck vazio
não reseta -- o cemitério dele fica onde está. Inverter os dois passos é a
única troca de ordem que nenhum teste de contagem de mão pegaria.

Este módulo escrevia só o passo 3, na feature 003, com os dois primeiros
previstos para "ficarem em volta" quando a §9 entrasse. Eles entraram, e
ficaram aqui mesmo: o movimento é `_take_from_deck_top`, privado, e a regra é
a única superfície pública. Duas portas deixariam a mais curta de digitar ser
a que pula as guardas.

Quem executa o reset é `deck_reset.py`. Quem decide se ele acontece é este
módulo.
"""

from apps.game.match import Match, MatchCard, PlayerState
from apps.game.randomness import RandomSource

from .deck_reset import reset_deck_from_graveyard

# Fluxo de Partida §12. Mora aqui, e não em `player_state.py`, porque aplicar
# o teto é regra -- e aquele arquivo diz isso de si mesmo. É também a única
# aplicação dele no jogo inteiro: a §8 registra que não existe descarte por
# excesso de mão.
MAX_HAND_SIZE = 10


class NegativeDrawCountError(Exception):
    """Pediram uma quantidade negativa de compras, citando o valor.

    Comprar 0 é válido -- o mulligan de 0 cartas repõe 0. Negativo é conta
    errada de quem chamou, e sem esta recusa passaria despercebido como
    "comprei 0", porque `range(-3)` é vazio.
    """

    def __init__(self, count: int) -> None:
        super().__init__(f"cannot draw {count} cards: expected a count of 0 or more")
        self.count = count


def draw_card(
    match: Match, user_id: int, *, randomness: RandomSource
) -> MatchCard | None:
    """A §9 inteira: guarda de mão, reset de deck, e então a compra.

    Devolve a carta que entrou na mão, ou `None` quando a compra **não
    aconteceu**. `None` não é erro nem recusa: é a resposta do jogo para a mão
    cheia, e quem chamou segue normalmente -- o Upkeep da §4 não trata exceção
    porque um jogador está com a mão cheia.

    Consome um sorteio da partida se, e só se, um reset acontecer.

    >>> draw_card(match, 7, randomness=source).card_id
    15
    >>> draw_card(match, 7, randomness=source) is None   # mão em 10
    True
    """
    player = match.player(user_id)

    if len(player.hand) >= MAX_HAND_SIZE:
        return None

    if not player.deck and not _restock_deck(match, player, randomness):
        return None

    return _take_from_deck_top(player)


def draw_cards(
    match: Match, user_id: int, count: int, *, randomness: RandomSource
) -> list[MatchCard]:
    """`count` compras, cada uma passando pelas guardas na sua vez.

    Devolve as cartas que efetivamente entraram na mão, na ordem em que
    entraram; `len()` é quantas foram. Comprar 3 com 8 na mão devolve 2 cartas
    e deixa a mão em 10, nunca em 11.

    Para na primeira compra que não acontece: os dois motivos para `None` --
    mão cheia, e nada de onde comprar -- não se desfazem sozinhos no meio de um
    laço.

    >>> len(draw_cards(match, 7, 4, randomness=source))
    4
    """
    if count < 0:
        raise NegativeDrawCountError(count)

    drawn: list[MatchCard] = []

    for _ in range(count):
        card = draw_card(match, user_id, randomness=randomness)

        if card is None:
            break

        drawn.append(card)

    return drawn


def _restock_deck(match: Match, player: PlayerState, randomness: RandomSource) -> bool:
    """Reseta o deck pelo cemitério, ou diz que não havia o que resetar.

    O `False` é o caso que a §9 não responde: deck vazio e cemitério vazio.
    Não acontece em partida legal -- as 40 cartas de um jogador não cabem entre
    mão (teto de 10), banco (teto de 6) e pilha --, então isto é defesa contra
    estado corrompido. Devolve em vez de levantar porque levantar mataria a
    partida exatamente pelo motivo que a §9 proíbe.

    Cunha o sorteio só depois de saber que o reset vai acontecer: assim uma
    compra que não acontece não gasta um ponto da sequência da partida.
    """
    if not player.graveyard:
        return False

    reset_deck_from_graveyard(player, randomness=randomness, roll=match.mint_roll())

    return True


def _take_from_deck_top(player: PlayerState) -> MatchCard:
    """Move a carta do topo do deck para o fim da mão, e devolve a carta.

    O topo é `deck[0]`, como `player_state.py` fixou. A carta mantém o
    identificador que já tinha -- trocar de zona não cunha identidade nova.

    Privada porque é o passo 3 sozinho, sem as guardas. O único chamador é
    `draw_card`, que só chega aqui depois de provar que o deck tem carta.
    """
    drawn = player.deck.pop(0)
    player.hand.append(drawn)

    return drawn
