"""O mulligan da §3: a única decisão de jogador em todo o setup, e a única
coisa simultânea da partida inteira.

A ordem das operações é a regra, e errá-la muda o jogo:

    (a) as cartas escolhidas saem da mão e ficam de lado
    (b) o jogador compra do deck a mesma quantidade que devolveu
    (c) só então as separadas voltam para o deck
    (d) o deck é reembaralhado

O que essa ordem garante: uma carta jogada fora no mulligan não pode ser
recomprada na hora. Com (c) antes de (b), ela poderia -- e nenhum teste de
contagem perceberia a troca.

Cada jogador executa os quatro passos assim que a resposta dele chega; o setup
só espera os dois para o sorteio do token. A consequência é que a ordem de
chegada faz parte da entrada: dois setups com as mesmas escolhas e a mesma
semente, mas com as respostas chegando trocadas, produzem partidas diferentes.
É comportamento definido, e está registrado na spec da feature.
"""

from collections.abc import Sequence

from apps.game.match import CardInstanceId, Match, MatchCard, PlayerState
from apps.game.randomness import RandomSource

from .card_draw import draw_cards
from .match_setup import finish_setup
from .player_action import CardNotInHandError


class MulliganAlreadyTakenError(Exception):
    """Este jogador já respondeu. É uma vez por jogador por partida.

    Também é a recusa de um mulligan que chega depois do setup terminado: com
    os dois marcados, não sobra janela aberta e a pergunta é a mesma.
    """

    def __init__(self, user_id: int, match_id: str) -> None:
        super().__init__(
            f"user {user_id} already took the mulligan in match {match_id!r}: "
            f"expected at most 1 mulligan per player per match"
        )
        self.user_id = user_id
        self.match_id = match_id


def record_mulligan(
    match: Match,
    user_id: int,
    selection: Sequence[CardInstanceId],
    *,
    randomness: RandomSource,
) -> None:
    """A escolha de um jogador, aplicada na ordem que a §3 exige.

    Valida tudo antes de mutar qualquer coisa: `user_id` de fora, mulligan
    repetido e carta fora da mão deixam mão, deck e marca exatamente como
    estavam.

    Trocar 0 cartas é escolha válida e resposta completa -- diferente de ainda
    não ter respondido.

    Quando este é o segundo mulligan, o setup fecha aqui mesmo.

    >>> record_mulligan(match, 7, [], randomness=source)
    >>> match.awaiting_mulligan_user_ids
    (9,)
    """
    player = match.player(user_id)

    if player.mulligan_taken:
        raise MulliganAlreadyTakenError(user_id, match.match_id)

    returned = _cards_from_hand(player, selection)

    _swap_returned_cards(player, returned, match, randomness)
    player.mulligan_taken = True

    finish_setup(match, randomness=randomness)


def _cards_from_hand(
    player: PlayerState, selection: Sequence[CardInstanceId]
) -> list[MatchCard]:
    """Resolve a seleção inteira contra a mão, antes de tocar em nada.

    Consome uma cópia da mão ao casar, então citar o mesmo identificador duas
    vezes cai na mesma recusa de uma carta que não está lá -- que é o que ele
    é, na segunda ocorrência.
    """
    candidates = list(player.hand)
    found: list[MatchCard] = []

    for card_instance_id in selection:
        card = _take_candidate(candidates, card_instance_id)

        if card is None:
            raise CardNotInHandError(
                card_instance_id,
                player.user_id,
                [held.card_instance_id for held in player.hand],
            )

        found.append(card)

    return found


def _take_candidate(
    candidates: list[MatchCard], card_instance_id: CardInstanceId
) -> MatchCard | None:
    """Tira o candidato da lista, para que ele não case duas vezes."""
    for index, card in enumerate(candidates):
        if card.card_instance_id == card_instance_id:
            return candidates.pop(index)

    return None


def _swap_returned_cards(
    player: PlayerState,
    returned: list[MatchCard],
    match: Match,
    randomness: RandomSource,
) -> None:
    """Os quatro passos, nesta ordem. A ordem é a regra -- veja o topo."""
    for card in returned:
        player.hand.remove(card)

    draw_cards(match, player.user_id, len(returned), randomness=randomness)

    player.deck.extend(returned)
    player.deck = randomness.shuffled(player.deck, match.mint_roll())
