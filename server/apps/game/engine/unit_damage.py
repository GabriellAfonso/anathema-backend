"""O que o dano faz com uma unidade, e o que acontece com quem morre.

Só alteração. As perguntas -- vida máxima, vida restante, morta, imune -- moram
em `unit_vitals.py`, e a separação é a razão de mudar de cada um.

Dano **acumula** em `BankUnit.damage_taken`; ele não reduz vida diretamente. O
docstring daquele campo registra por quê: guardar vida absoluta obrigaria a
desfazer na mão a expiração de um buff de vida temporário, e o resultado
passaria a depender da ordem dos eventos.

Dano também **não é modificador**: não expira, e a varredura do Fim de Rodada
(§8) não o toca.
"""

from apps.game.cards import CardCatalog
from apps.game.match import BankUnit, DamageImmunity, Match, PlayerState

from .unit_vitals import unit_has_damage_immunity, unit_is_dead


def deal_damage_to_unit(unit: BankUnit, amount: int) -> None:
    """Acumula dano na unidade. Uma barreira absorve o dano inteiro e some.

    Fluxo de Partida §14, corrigido em 2026-09-11: a MAGIC BARRIER ignora o
    **próximo** dano, de qualquer fonte. Dano de 0 não é dano -- um atacante com
    ataque efetivo 0 não gasta a barreira de ninguém.

    Não remove a unidade morta: quem faz isso é `bury_dead_units`, sobre os dois
    bancos, porque `BankUnit` não sabe de quem é.

    O feitiço que acerta uma unidade com barreira é aceito e só gasta a
    barreira -- o alvo está em campo, o efeito foi aplicado.

    >>> deal_damage_to_unit(unit, 3)
    >>> unit.damage_taken
    3
    """
    if amount <= 0:
        return

    if unit_has_damage_immunity(unit):
        _break_barrier(unit)
        return

    unit.damage_taken += amount


def _break_barrier(unit: BankUnit) -> None:
    """Tira a barreira que acabou de absorver um dano. Há no máximo uma: a
    MAGIC BARRIER não acumula."""
    unit.modifiers = [
        modifier
        for modifier in unit.modifiers
        if not isinstance(modifier, DamageImmunity)
    ]


def bury_dead_units(match: Match, *, catalog: CardCatalog) -> None:
    """Move para o cemitério do **dono** toda unidade morta dos dois bancos.

    Varredura e não checagem do alvo por dois motivos. Descobrir o dono de um
    `BankUnit` exigiria varrer os jogadores de qualquer jeito -- ele contém o
    `MatchCard` e nada mais. E o dano da §7.3 é simultâneo: o combate vai matar
    várias unidades dos dois lados num evento só, e esta é a forma que ele já
    precisa.

    Mais larga que o necessário nesta feature, de propósito: nenhum dos cinco
    efeitos mata quem não seja o alvo, e nenhum reduz vida máxima.

    >>> bury_dead_units(match, catalog=catalog)
    """
    for player in match.players:
        _bury_dead_in_bank(player, catalog=catalog)


def _bury_dead_in_bank(player: PlayerState, *, catalog: CardCatalog) -> None:
    """Parte o banco de um jogador em vivos e mortos, numa passagem.

    Compara por `card_instance_id`, nunca por `==` entre `BankUnit`: a
    dataclass tem `__eq__` gerado, e duas cópias intactas da mesma carta são
    iguais por valor -- uma remoção por valor levaria as duas.

    O `MatchCard` que entra no cemitério não tem onde guardar dano nem
    modificador, então eles ficam para trás por construção.
    """
    dead_ids = {
        unit.card.card_instance_id
        for unit in player.bank
        if unit_is_dead(unit, catalog=catalog)
    }

    if not dead_ids:
        return

    player.graveyard.extend(
        unit.card for unit in player.bank if unit.card.card_instance_id in dead_ids
    )
    player.bank = [
        unit for unit in player.bank if unit.card.card_instance_id not in dead_ids
    ]
