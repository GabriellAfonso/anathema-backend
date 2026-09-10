"""O início da partida (§3): de dois decks a uma partida pronta para o Upkeep.

Roda uma vez, e em duas metades separadas por uma espera. `start_match` faz o
que não depende de decisão de jogador -- validar, materializar, embaralhar,
comprar 4 -- e para na espera do mulligan. `finish_setup` faz o que só pode
acontecer depois que os dois responderam: sortear o token, compensar quem não
o recebeu, e posicionar a partida para o Upkeep da Rodada 1.

Executar o Upkeep é da §4, e não é daqui.
"""

from dataclasses import dataclass
from uuid import uuid4

from apps.game.cards import CardCatalog, CardId, Deck, DeckProblem, deck_problems
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchCard,
    MatchPhase,
    PlayerState,
)
from apps.game.randomness import RandomSeed, RandomSource
from apps.players.services.player_queries import PlayerData

from .card_draw import draw_from_deck_top

# Fluxo de Partida §12.
OPENING_HAND_SIZE = 4


@dataclass(frozen=True, slots=True)
class MatchEntry:
    """Um jogador chegando à partida com o deck dele.

    Perfil e deck viajam juntos para que não possam ser trocados de par: com
    quatro parâmetros posicionais, dar o deck de um ao perfil do outro é um
    erro que nenhum tipo pega.

    >>> MatchEntry(profile=await get_player_public_data(7), deck=deck).deck[0]
    15
    """

    profile: PlayerData
    deck: Deck


class InvalidPlayerDeckError(Exception):
    """Deck recusado, dizendo de quem era e todos os problemas de uma vez.

    Envolve `deck_problems()` da feature 001; nenhuma das três regras de deck
    é reescrita aqui. O que esta camada acrescenta é o dono, que a validação
    sozinha não tem como saber.

    >>> raise InvalidPlayerDeckError(7, problems)
    InvalidPlayerDeckError: deck of user 7 was refused: deck has 39 cards,
    expected exactly 40
    """

    def __init__(self, user_id: int, problems: tuple[DeckProblem, ...]) -> None:
        super().__init__(
            f"deck of user {user_id} was refused: "
            + "; ".join(problem.message for problem in problems)
        )
        self.user_id = user_id
        self.problems = problems


def start_match(
    first: MatchEntry,
    second: MatchEntry,
    *,
    catalog: CardCatalog,
    randomness: RandomSource,
    seed: RandomSeed,
) -> Match:
    """A §3 até a espera do mulligan.

    Os dois decks são validados antes de qualquer outra coisa: deck recusado
    não deixa partida nenhuma nascer, e não existe partida com um lado só.

    A partida volta em `MatchPhase.MULLIGAN`, sem dono de token e sem
    prioridade -- quem sorteia é `finish_setup`, quando os dois responderem.

    >>> match = start_match(one, two, catalog=catalog,
    ...                     randomness=SeededRandomSource(), seed=seed)
    >>> len(match.players[0].hand), len(match.players[0].deck)
    (4, 36)
    """
    _ensure_valid_entry(first, catalog)
    _ensure_valid_entry(second, catalog)

    match = Match(
        match_id=str(uuid4()),
        players=(
            PlayerState(profile=first.profile),
            PlayerState(profile=second.profile),
        ),
        random_seed=seed,
    )

    _deal_opening_hand(match, match.players[0], first.deck, randomness)
    _deal_opening_hand(match, match.players[1], second.deck, randomness)

    return match


def finish_setup(match: Match, *, randomness: RandomSource) -> None:
    """Sorteia o token, compensa o oponente e posiciona para o Upkeep.

    Não faz nada enquanto houver mulligan pendente: é `record_mulligan` quem a
    chama, e o segundo jogador a responder é quem dispara.

    A compensação da §3 acontece **depois** do mulligan porque só aqui se sabe
    quem vai recebê-la -- antes do sorteio ninguém é o oponente do dono do
    token.

    >>> finish_setup(match, randomness=source)
    >>> match.phase
    <MatchPhase.UPKEEP: 'upkeep'>
    """
    if match.awaiting_mulligan_user_ids:
        return

    holder = randomness.choose(match.players, match.mint_roll())

    draw_from_deck_top(match.opponent_of(holder.user_id))

    match.token_holder_user_id = holder.user_id
    match.priority_user_id = holder.user_id
    match.phase = MatchPhase.UPKEEP


def _ensure_valid_entry(entry: MatchEntry, catalog: CardCatalog) -> None:
    """Recusa nomeando o dono e todos os problemas, nunca só o primeiro."""
    problems = deck_problems(entry.deck, catalog)

    if problems:
        raise InvalidPlayerDeckError(entry.profile["user_id"], problems)


def _deal_opening_hand(
    match: Match, player: PlayerState, deck: Deck, randomness: RandomSource
) -> None:
    """Materializa, embaralha e compra 4 -- os passos 2, 3 e 5 da §3."""
    cards = _mint_deck(match, deck)
    player.deck = randomness.shuffled(cards, match.mint_roll())

    for _ in range(OPENING_HAND_SIZE):
        draw_from_deck_top(player)


def _mint_deck(match: Match, deck: Deck) -> list[MatchCard]:
    """Cada identificador do deck vira uma carta concreta desta partida.

    Três cópias do mesmo `card_id` viram três cartas distintas: é a partida
    que cunha a identidade, e o espaço é único nela.
    """
    return [_mint_card(match, card_id) for card_id in deck]


def _mint_card(match: Match, card_id: CardId) -> MatchCard:
    instance_id: CardInstanceId = match.mint_card_instance_id()

    return MatchCard(card_instance_id=instance_id, card_id=card_id)
