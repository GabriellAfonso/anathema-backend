"""O dano da §7.3: todos os pares e o Nexus, num evento só.

**Planeja antes de aplicar.** O ataque efetivo de todos os participantes é lido
antes da primeira escrita, e é isso que torna a simultaneidade da §7.3 uma
propriedade estrutural em vez de uma coincidência. Aplicar dentro do laço daria
o mesmo resultado hoje -- dano acumulado não altera ataque efetivo, e o enterro
só acontece depois --, mas o resultado passaria a depender dessas duas coisas
não mudarem.

É o mesmo movimento que `round_end._lasting_modifiers` faz ao devolver lista
nova "para não mutar durante a leitura".

**Ninguém morre aqui.** Este módulo acumula dano e altera Nexus; a varredura da
§7.4 é de `combat_cleanup.py`, e chama a `bury_dead_units` que já existe. É essa
separação que faz "nenhuma unidade morre antes de ter causado o dano dela" valer
por construção.

A revalidação é por identificador, como a da §6: entre a declaração e a
resolução um feitiço do defensor pode ter matado um atacante, e `CombatState`
guarda identificador justamente para que a pergunta "ele ainda está em campo?"
possa ser feita aqui.
"""

from apps.game.cards import CardCatalog
from apps.game.match import (
    BankUnit,
    CardInstanceId,
    CombatState,
    Match,
    NotAParticipantError,
    PlayerState,
)

from .unit_damage import deal_damage_to_unit
from .unit_vitals import unit_effective_attack
from .victory import change_nexus

# Um golpe planejado: em quem bate, e quanto. Tupla e não dataclass -- são dois
# campos sem invariante própria, e a lista deles vive dentro de uma chamada só.
CombatStrike = tuple[BankUnit, int]


def resolve_combat_damage(match: Match, *, catalog: CardCatalog) -> None:
    """Todo o dano do combate, num evento só, e a §10 apurada no fim.

    Só o Nexus do defensor muda: o do atacante nunca recebe dano de combate
    (FR-057). Até a correção da nota de 2026-09-11 os dois entravam numa
    apuração simultânea, para o empate da §10; sem empate, o dano do defensor
    passa por `change_nexus` como qualquer outra alteração de Nexus.

    >>> resolve_combat_damage(match, catalog=catalog)
    >>> defender.nexus
    13
    """
    combat = match.ongoing_combat()
    attacker_player = _attacking_player(match)
    defender = match.opponent_of(attacker_player.user_id)

    strikes, nexus_damage = _plan_combat_damage(match, combat, catalog=catalog)

    for unit, amount in strikes:
        deal_damage_to_unit(unit, amount)

    change_nexus(match, defender, -nexus_damage)


def _attacking_player(match: Match) -> PlayerState:
    """O dono do token, que é quem declarou (§5C).

    O `None` é estado corrompido, não fluxo: o combate só é alcançável da Fase
    de Ação, que só existe depois do sorteio do token na §3. Recusa nomeada em
    vez de `assert` -- que some com `-O` -- e de `cast`, que calaria o mypy sem
    responder. É o mesmo tratamento de `round_end._swap_token`.
    """
    holder = match.token_holder_user_id

    if holder is None:
        raise NotAParticipantError(holder, match.match_id)

    return match.player(holder)


def _plan_combat_damage(
    match: Match, combat: CombatState, *, catalog: CardCatalog
) -> tuple[list[CombatStrike], int]:
    """Os golpes e o total que chega ao Nexus, sem escrever nada.

    A ordem da declaração é percorrida, e não influencia o resultado: nada é
    lido depois de escrito.
    """
    strikes: list[CombatStrike] = []
    nexus_damage = 0

    for attacker_card_instance_id in combat.attacker_card_instance_ids:
        pair, to_nexus = _plan_one_attacker(
            match, combat, attacker_card_instance_id, catalog=catalog
        )
        strikes.extend(pair)
        nexus_damage += to_nexus

    return strikes, nexus_damage


def _plan_one_attacker(
    match: Match,
    combat: CombatState,
    attacker_card_instance_id: CardInstanceId,
    *,
    catalog: CardCatalog,
) -> tuple[list[CombatStrike], int]:
    """Um atacante declarado. Quatro casos, e três deles não tocam o Nexus.

    | atacante em campo | bloqueador declarado | bloqueador em campo | resultado |
    |---|---|---|---|
    | não | -- | -- | nada (o bloqueador dele fica órfão) |
    | sim | não | -- | ataque efetivo no Nexus do defensor |
    | sim | sim | sim | os dois trocam dano, nada ao Nexus |
    | sim | sim | não | nada, e **nada ao Nexus** |

    A última linha não é alcançável com as cinco cartas do MVP -- o atacante é
    espectador e nenhum feitiço do defensor mata unidade do próprio dono --, e
    precisa de resposta porque o código tem de ter um braço. A escolhida é a que
    a §7.3 sustenta: estar bloqueado é propriedade da **declaração**, não da
    sobrevivência do bloqueador, e "Bloqueado: nenhum dano chega ao Nexus".
    Também é a simétrica da regra do órfão -- quando um dos dois some, o outro
    não troca dano com ninguém.
    """
    attacker = match.bank_unit(attacker_card_instance_id)

    if attacker is None:
        return [], 0

    blocker = _blocker_on_the_battlefield(match, combat, attacker_card_instance_id)

    if blocker is None:
        return _unblocked(combat, attacker_card_instance_id, attacker, catalog)

    return _trade(attacker, blocker, catalog), 0


def _blocker_on_the_battlefield(
    match: Match, combat: CombatState, attacker_card_instance_id: CardInstanceId
) -> BankUnit | None:
    """O bloqueador daquele atacante, se ele foi atribuído **e** está em campo."""
    blocker_card_instance_id = combat.blocker_of(attacker_card_instance_id)

    if blocker_card_instance_id is None:
        return None

    return match.bank_unit(blocker_card_instance_id)


def _unblocked(
    combat: CombatState,
    attacker_card_instance_id: CardInstanceId,
    attacker: BankUnit,
    catalog: CardCatalog,
) -> tuple[list[CombatStrike], int]:
    """Atacante sem bloqueador em campo.

    Passa direto ao Nexus **só** se ninguém foi declarado na frente dele. Um
    bloqueador declarado que sumiu deixa o atacante bloqueado e sem par: nada
    acontece, e nada chega ao Nexus.
    """
    if combat.blocker_of(attacker_card_instance_id) is not None:
        return [], 0

    return [], unit_effective_attack(attacker, catalog=catalog)


def _trade(
    attacker: BankUnit, blocker: BankUnit, catalog: CardCatalog
) -> list[CombatStrike]:
    """Os dois causam um no outro dano igual ao próprio ataque efetivo.

    Os dois valores são lidos **antes** de qualquer escrita -- os golpes
    voltam planejados, e quem aplica é `resolve_combat_damage`.
    """
    return [
        (blocker, unit_effective_attack(attacker, catalog=catalog)),
        (attacker, unit_effective_attack(blocker, catalog=catalog)),
    ]
