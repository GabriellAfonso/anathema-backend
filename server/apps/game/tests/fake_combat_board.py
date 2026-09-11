"""Um tabuleiro pronto para exercitar a §7, com as cartas reais do MVP.

Fica sobre `fake_spell_board.py` em vez de repeti-lo: a montagem é a mesma —
mão e banco com identidade cunhada pela partida, energia de sobra, Fase de Ação
com o token no primeiro jogador — e o que muda é **quais** cartas, e o
posicionamento em Combate.

As unidades são escolhidas pelo par (ataque, vida), que é o que a §7.3 mede:

    DARK AGE  3/2   morre para quase tudo e mata MORTEM
    KHRAS     2/4   sobrevive a um golpe de 3
    SKILLET   4/5   bloqueador que aguenta
    POLAROID  2/6   bate fraco e não morre
    MORTEM    7/2   mata qualquer um e morre para qualquer um

A troca canônica de mútua destruição é DARK AGE contra MORTEM: 3 de dano numa
vida 2 e 7 de dano numa vida 2, os dois morrem.

`declare_combat` põe a partida em Combate **sem** passar pela ação da §5C, de
propósito: os testes da §7.2 e da §7.3 exercitam o bloqueio e o dano, e
depender da declaração faria uma falha lá reprovar arquivos que não são sobre
ela. Quem testa a declaração é `test_declare_attack.py`, e esse passa pela
ação.
"""

from apps.game.cards import CardCatalog, CardId
from apps.game.match import (
    CardInstanceId,
    CombatState,
    Match,
    MatchPhase,
    PlayerState,
)
from apps.game.tests.fake_spell_board import (
    LIFE_POTION,
    MAGIC_BARRIER,
    SACRIFICIAL_FIRE,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    bank_card,
    fake_spell_board,
    hand_card,
)
from apps.game.tests.fake_match_state import PLAYER_ONE, PLAYER_TWO

# Unidades do MVP escolhidas pelo par (ataque, vida) -- ver o cabeçalho.
DARK_AGE = CardId(5)
KHRAS = CardId(6)
SKILLET = CardId(7)
POLAROID = CardId(13)
MORTEM = CardId(3)


def fake_combat_board(
    *,
    catalog: CardCatalog,
    hand_one: tuple[CardId, ...] = (),
    hand_two: tuple[CardId, ...] = (),
    bank_one: tuple[CardId, ...] = (DARK_AGE,),
    bank_two: tuple[CardId, ...] = (KHRAS,),
) -> Match:
    """Partida na Fase de Ação, token e prioridade no primeiro jogador, e as
    unidades pedidas nos dois bancos.

    As mãos vêm vazias por default: a maior parte dos testes do combate não
    lança feitiço nenhum, e uma mão cheia só acrescentaria cartas que nenhuma
    afirmação menciona.

    >>> match = fake_combat_board(catalog=mvp_catalog())
    >>> match.phase
    <MatchPhase.ACTION: 'action'>
    """
    return fake_spell_board(
        catalog=catalog,
        hand_one=hand_one,
        hand_two=hand_two,
        bank_one=bank_one,
        bank_two=bank_two,
    )


def declare_combat(match: Match, *attacker_indexes: int) -> CombatState:
    """Põe a partida em Combate com aquelas posições do banco do atacante.

    Atalho de **estado**, não de regra: escreve os campos que declarar e
    **Atacar** (§7.1) deixariam, sem passar pelas ações -- a partida sai já na
    janela do defensor. Devolve o `CombatState` para o teste
    poder afirmar sobre ele sem reler `match.combat`.

    >>> declare_combat(match, 0, 1).attacker_card_instance_ids
    [3, 4]
    """
    attacker = match.players[0]

    match.token_consumed = True
    match.combat = CombatState(
        attacker_card_instance_ids=[
            bank_card(attacker, index) for index in attacker_indexes
        ]
    )
    match.phase = MatchPhase.COMBAT
    match.priority_user_id = match.players[1].user_id
    match.consecutive_passes = 0

    return match.combat


def unit_damage(player: PlayerState, card_instance_id: CardInstanceId) -> int:
    """O dano acumulado daquela unidade, ou -1 se ela não está mais no banco.

    O -1 é sentinela de teste, e só existe porque a afirmação "ela morreu" e a
    afirmação "ela levou 3" são escritas lado a lado nos testes de dano.

    >>> unit_damage(defender, blocker)
    3
    """
    for unit in player.bank:
        if unit.card.card_instance_id == card_instance_id:
            return unit.damage_taken

    return -1


def in_graveyard(player: PlayerState, card_instance_id: CardInstanceId) -> bool:
    """Se aquela carta está no cemitério do jogador.

    >>> in_graveyard(attacker, dead)
    True
    """
    return any(card.card_instance_id == card_instance_id for card in player.graveyard)


__all__ = [
    "PLAYER_ONE",
    "PLAYER_TWO",
    "DARK_AGE",
    "KHRAS",
    "SKILLET",
    "POLAROID",
    "MORTEM",
    "SOMEONES_SHIELD",
    "MAGIC_BARRIER",
    "SACRIFICIAL_FIRE",
    "LIFE_POTION",
    "SUMMONED_AX",
    "fake_combat_board",
    "declare_combat",
    "unit_damage",
    "in_graveyard",
    "bank_card",
    "hand_card",
]
