"""As quatro guardas que todo lançamento de feitiço faz, e as cinco recusas
delas.

Nasceram em `cast_spell.py` e subiram para cá na feature 007, quando dois
caminhos lançavam feitiço com as mesmas perguntas na mesma ordem. Desde a
feature 008 o caminho é um só -- `cast_spell`, nas duas fases --, e as guardas
ficaram aqui: com as cinco recusas elas formam um módulo coeso por si, e é o
mesmo movimento que a feature 006 fez ao subir `card_in_hand` e
`ensure_enough_energy` para `player_action.py`.

    1. a carta citada está na mão do autor
    2. a carta é um feitiço
    3. a energia atual cobre o custo
    4. o alvo casa com o que o efeito declara

A carta precisa ser resolvida antes da terceira -- sem ela não há custo a citar
na recusa de energia --, e o efeito antes da quarta -- sem ele não há
`TargetKind` a citar na recusa de alvo.

**Nada aqui altera a partida.** As quatro perguntas acontecem antes da primeira
atribuição de quem chama, e é essa ordem que garante que uma recusa deixa o
estado idêntico.

A porta devolve o `BankUnit` do alvo, e não só valida o lado: `cast_spell`
aplica o efeito na mesma chamada, e precisa dele.

O motor decide exigência de alvo, tipo de alvo e duração pelos campos
estruturados do catálogo. Regra que dependa de `Spell.description` é bug, e
`cards/effects.py` diz isso de si mesmo.
"""

from dataclasses import dataclass

from apps.game.cards import CardCatalog, CardType, Spell, TargetKind
from apps.game.match import (
    BankUnit,
    CardInstanceId,
    Match,
    MatchCard,
    MatchPhase,
    PlayerState,
)

from .blocker_pairing import UnitIsNotAttackingError
from .player_action import (
    CastSpellAction,
    IllegalActionError,
    card_in_hand,
    ensure_enough_energy,
)


class CardIsNotASpellError(IllegalActionError):
    """Usaram uma ação de lançar feitiço com uma carta que é unidade.

    Simétrica de `CardIsNotAUnitError`, e recusa pelo mesmo motivo: usar a ação
    errada não é atalho para a certa.

    >>> raise CardIsNotASpellError(card, CardType.UNIT)
    CardIsNotASpellError: card instance 3 (card 15) is a unit: expected a spell
    """

    def __init__(self, card: MatchCard, card_type: CardType) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) "
            f"is a {card_type}: expected a spell"
        )
        self.card_instance_id = card.card_instance_id
        self.card_type = card_type


class SpellTakesNoTargetError(IllegalActionError):
    """O efeito não aceita alvo e a jogada mandou um.

    Recusa e não parâmetro ignorado: um alvo que o efeito não sabe usar é
    jogada mal formada, e ignorá-lo esconderia um cliente quebrado.

    >>> raise SpellTakesNoTargetError(card, CardInstanceId(11))
    SpellTakesNoTargetError: card instance 3 (card 1004) takes no target: got
    card instance 11
    """

    def __init__(
        self, card: MatchCard, target_card_instance_id: CardInstanceId
    ) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) "
            f"takes no target: got card instance {target_card_instance_id}"
        )
        self.card_instance_id = card.card_instance_id
        self.target_card_instance_id = target_card_instance_id


class SpellNeedsTargetError(IllegalActionError):
    """O efeito exige alvo e a jogada não mandou. Cita o tipo esperado.

    >>> raise SpellNeedsTargetError(card, TargetKind.ENEMY_UNIT)
    SpellNeedsTargetError: card instance 3 (card 1005) needs a target: expected
    an 'enemy_unit'
    """

    def __init__(self, card: MatchCard, expected: TargetKind) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) "
            f"needs a target: expected an '{expected}'"
        )
        self.card_instance_id = card.card_instance_id
        self.expected = expected


class WrongSpellTargetSideError(IllegalActionError):
    """O alvo está em campo, no banco errado.

    "Aliado" e "inimigo" são relativos a **quem lança**, e é essa relatividade
    que a recusa cita.

    Distinta de `SpellTargetNotOnBattlefieldError` de propósito: uma é uma tela
    que ofereceu um alvo que a carta não aceita, a outra é uma tela
    desatualizada, e colapsá-las esconderia qual das duas está quebrada.

    >>> raise WrongSpellTargetSideError(CardInstanceId(11), TargetKind.ALLIED_UNIT, 9)
    WrongSpellTargetSideError: card instance 11 belongs to user 9: expected an
    'allied_unit' of the caster
    """

    def __init__(
        self,
        target_card_instance_id: CardInstanceId,
        expected: TargetKind,
        owner_user_id: int,
    ) -> None:
        super().__init__(
            f"card instance {target_card_instance_id} belongs to user "
            f"{owner_user_id}: expected an '{expected}' of the caster"
        )
        self.target_card_instance_id = target_card_instance_id
        self.expected = expected
        self.owner_user_id = owner_user_id


class SpellTargetNotOnBattlefieldError(IllegalActionError):
    """O alvo não está em banco nenhum, no momento do lançamento.

    É sempre recusa, e nunca um feitiço aceito que não faz nada: o efeito é
    aplicado na mesma chamada que valida o alvo, então não existe intervalo em
    que ele pudesse sumir.

    >>> raise SpellTargetNotOnBattlefieldError(CardInstanceId(11))
    SpellTargetNotOnBattlefieldError: card instance 11 is not on the
    battlefield: expected a unit in a bank
    """

    def __init__(self, target_card_instance_id: CardInstanceId) -> None:
        super().__init__(
            f"card instance {target_card_instance_id} is not on the "
            f"battlefield: expected a unit in a bank"
        )
        self.target_card_instance_id = target_card_instance_id


class SpellOnlyInDeclarationError(IllegalActionError):
    """Um feitiço de regra própria jogado fora do momento dele (§14).

    O SACRIFICIAL FIRE só vale na declaração de ataque, e só o atacante tem a
    vez nela -- então esta recusa cobre também o defensor que tenta jogá-lo na
    janela dele.

    >>> raise SpellOnlyInDeclarationError(card, MatchPhase.ACTION)
    SpellOnlyInDeclarationError: card instance 3 (card 1003) can only be cast
    in the declaration: the match is in phase 'action'
    """

    def __init__(self, card: MatchCard, phase: MatchPhase) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) can "
            f"only be cast in the {MatchPhase.DECLARATION}: the match is in "
            f"phase '{phase}'"
        )
        self.card_instance_id = card.card_instance_id
        self.phase = phase


@dataclass(frozen=True, slots=True)
class ValidatedSpellCast:
    """O que as quatro guardas apuraram, para quem chamou não reapurar.

    `target is None` significa que o efeito **não mira nada**. Não tem outro
    significado: a guarda recusa alvo fora de campo, e o efeito vem logo depois.

    >>> validated.spell.energy
    2
    """

    card: MatchCard
    spell: Spell
    target: BankUnit | None


def validated_spell_cast(
    match: Match,
    actor: PlayerState,
    action: CastSpellAction,
    *,
    catalog: CardCatalog,
) -> ValidatedSpellCast:
    """As quatro guardas da §5B, na ordem, sem aplicar nada.

    Recebe a ação inteira. Até a feature 008 recebia os dois identificadores
    soltos, porque dois tipos de ação diferentes a chamavam; hoje é um só.

    >>> validated_spell_cast(match, actor, CastSpellAction(7, CardInstanceId(3)),
    ...                      catalog=catalog).spell.energy
    4
    """
    card = card_in_hand(actor, action.card_instance_id)
    spell = _as_spell(card, catalog)

    _ensure_castable_in_this_phase(match, card, spell)
    ensure_enough_energy(actor, card, spell.energy)
    target = _validated_target(
        match, actor, card, spell, action.target_card_instance_id
    )

    return ValidatedSpellCast(card=card, spell=spell, target=target)


def _as_spell(card: MatchCard, catalog: CardCatalog) -> Spell:
    """Guarda 2: o molde da carta é um feitiço.

    `isinstance` e não comparação de faixa de `card_id`: a faixa é convenção de
    alocação e `cards/card.py` proíbe derivar tipo dela.
    """
    template = catalog.card(card.card_id)

    if not isinstance(template, Spell):
        raise CardIsNotASpellError(card, template.card_type)

    return template


def _ensure_castable_in_this_phase(match: Match, card: MatchCard, spell: Spell) -> None:
    """O momento permitido pelo feitiço (§5B, §14), entre a carta e o custo.

    Vem antes da energia pela mesma razão que a carta vem: é pergunta sobre a
    jogada, e a recusa de energia de um feitiço que nem podia ser jogado agora
    esconderia o erro de verdade.
    """
    if not spell.effect.declaration_only or match.phase is MatchPhase.DECLARATION:
        return

    raise SpellOnlyInDeclarationError(card, match.phase)


def _validated_target(
    match: Match,
    actor: PlayerState,
    card: MatchCard,
    spell: Spell,
    target_card_instance_id: CardInstanceId | None,
) -> BankUnit | None:
    """Guarda 4: o alvo casa com o que o efeito declara.

    Lê `effect.target_kind`, campo estruturado do catálogo, e nunca a descrição
    em português da carta.
    """
    expected = spell.effect.target_kind

    if expected is TargetKind.NONE:
        _reject_unwanted_target(card, target_card_instance_id)
        return None

    if target_card_instance_id is None:
        raise SpellNeedsTargetError(card, expected)

    return _target_on_the_right_side(match, actor, target_card_instance_id, expected)


def _reject_unwanted_target(
    card: MatchCard, target_card_instance_id: CardInstanceId | None
) -> None:
    """Feitiço sem alvo que recebeu um."""
    if target_card_instance_id is None:
        return

    raise SpellTakesNoTargetError(card, target_card_instance_id)


def _target_on_the_right_side(
    match: Match,
    actor: PlayerState,
    target_card_instance_id: CardInstanceId,
    expected: TargetKind,
) -> BankUnit:
    """A unidade alvo, se ela está no banco que o `TargetKind` manda.

    Duas recusas diferentes porque são dois erros de cliente diferentes: o alvo
    no banco errado é uma tela que ofereceu o que a carta não aceita; o alvo em
    banco nenhum é uma tela desatualizada.

    Usa `Match.bank_unit()` em vez de uma varredura própria -- a busca por
    identificador já existe, e o dono sai de qual banco a devolveu.
    """
    target = match.bank_unit(target_card_instance_id)

    if target is None:
        raise SpellTargetNotOnBattlefieldError(target_card_instance_id)

    owner_user_id = _owner_of(match, target_card_instance_id)

    if owner_user_id == _expected_owner(match, actor, expected):
        _ensure_attacking_when_asked(match, target_card_instance_id, expected)
        return target

    raise WrongSpellTargetSideError(
        target_card_instance_id, expected, owner_user_id or actor.user_id
    )


def _owner_of(match: Match, target_card_instance_id: CardInstanceId) -> int | None:
    """De quem é o banco em que o alvo está, ou `None` se ele não está em campo.

    `None` não é erro aqui: o chamador já tratou o alvo fora de campo, e esta
    resposta só distingue os dois bancos.
    """
    for player in match.players:
        if any(
            unit.card.card_instance_id == target_card_instance_id
            for unit in player.bank
        ):
            return player.user_id

    return None


def _expected_owner(match: Match, actor: PlayerState, expected: TargetKind) -> int:
    """De quem o alvo teria de ser. "Aliado" e "inimigo" são relativos a quem
    lança, e é aqui que essa relatividade vira um `user_id`."""
    if expected in (TargetKind.ALLIED_UNIT, TargetKind.ALLIED_ATTACKER):
        return actor.user_id

    return match.opponent_of(actor.user_id).user_id


def _ensure_attacking_when_asked(
    match: Match, target_card_instance_id: CardInstanceId, expected: TargetKind
) -> None:
    """`ALLIED_ATTACKER` pede, além do lado, a unidade na zona de ataque (§14).

    Só chega aqui na declaração -- a guarda de momento correu antes --, então o
    combate existe.
    """
    if expected is not TargetKind.ALLIED_ATTACKER:
        return

    combat = match.ongoing_combat()

    if not combat.is_attacking(target_card_instance_id):
        raise UnitIsNotAttackingError(
            target_card_instance_id,
            list(combat.attacker_card_instance_ids),
            match.match_id,
        )
