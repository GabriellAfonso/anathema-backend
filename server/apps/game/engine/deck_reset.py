"""O reset de deck da §9: todo o cemitério vira o novo deck, embaralhado.

Acontece quando uma compra encontra o deck vazio, e só então. Quem decide é a
regra da §9, em `card_draw.py`; aqui se executa o movimento, com as duas
pré-condições já verificadas por ela.

O reset é ilimitado -- acontece toda vez que o deck zerar, quantas vezes for.
Nenhuma partida acaba por deck acabado; só Nexus a 0 encerra (§9, §10). Por
isso não existe contador aqui, nem teto, nem registro de quantos já houve.
"""

from apps.game.match import PlayerState
from apps.game.randomness import RandomSource, Roll


def reset_deck_from_graveyard(
    player: PlayerState, *, randomness: RandomSource, roll: Roll
) -> None:
    """Move o cemitério inteiro para o deck, embaralhado. Nada mais é tocado.

    Não decide se o reset deve acontecer: assume o que a §9 já verificou -- o
    deck está vazio e o cemitério não. Chamada fora dessas condições, descarta
    um deck com cartas, e isso é bug de chamador, não caso de borda do jogo.

    O `Roll` chega pronto em vez de ser cunhado aqui para que o contador de
    sorteios da partida não avance quando a regra descobre que não há
    cemitério para resetar.

    As cartas voltam com a identidade que já tinham: são os mesmos objetos, e
    `Match.mint_card_instance_id` afirma o mesmo do outro lado. Uma unidade que
    morreu chega ao cemitério já como `MatchCard` -- o `BankUnit` com o dano e
    os modificadores ficou para trás na §7.4 --, então não há o que zerar aqui.

    >>> reset_deck_from_graveyard(player, randomness=source, roll=match.mint_roll())
    >>> player.graveyard
    []

    Mão e banco não são tocados: o reset é sobre as duas pilhas de carta, não
    sobre o que está em jogo.
    """
    player.deck = randomness.shuffled(player.graveyard, roll)
    player.graveyard = []
