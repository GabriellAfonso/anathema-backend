"""As quatro guardas que todo lançamento de feitiço faz, e as cinco recusas
delas.

Dois caminhos lançam feitiço, e os dois fazem as mesmas perguntas na mesma
ordem: a §5B, que empilha, e a §7.2, que resolve na hora. Escrevê-las duas vezes
seria duplicar a regra; deixá-las em `cast_spell.py` poria o módulo cujo
docstring diz "a ação B da §5" como dono das guardas de uma ação que não é da
§5.

É o mesmo movimento que a feature 006 fez ao subir `card_in_hand` e
`ensure_enough_energy` para `player_action.py`, e que a 005 tinha feito ao subir
`CardNotInHandError` de `mulligan.py`. A prova de que foi só mudança de casa é
`test_cast_spell.py` passar sem uma linha alterada.

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

A porta devolve o `BankUnit` do alvo, e não só valida o lado. O caminho da pilha
ignora o valor -- ele revalida por identificador na resolução, porque o alvo pode
sumir no caminho; o caminho do combate aplica o efeito na hora e precisa dele.

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
    PlayerState,
)

from .player_action import (
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

    **Não é fizzle.** Fizzle é o alvo sumir *entre* o lançamento e a resolução,
    e consome a jogada; isto a rejeita. Mesmo fato, momentos diferentes,
    respostas opostas. O feitiço imediato da §7.2 nunca fizzla, justamente
    porque nele não existe esse intervalo.

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


@dataclass(frozen=True, slots=True)
class ValidatedSpellCast:
    """O que as quatro guardas apuraram, para quem chamou não reapurar.

    `target is None` significa que o efeito **não mira nada**, nunca que o alvo
    sumiu -- a mesma separação que `StackEntry.target_card_instance_id` escreve.

    >>> validated.spell.energy
    2
    """

    card: MatchCard
    spell: Spell
    target: BankUnit | None


def validated_spell_cast(
    match: Match,
    actor: PlayerState,
    card_instance_id: CardInstanceId,
    target_card_instance_id: CardInstanceId | None,
    *,
    catalog: CardCatalog,
) -> ValidatedSpellCast:
    """As quatro guardas da §5B, na ordem, sem aplicar nem empilhar nada.

    Recebe os dois identificadores soltos e não a ação: os dois braços que a
    chamam são tipos diferentes -- `CastSpellAction` e `CastCombatSpellAction`
    --, e pedir "uma ação com estes dois campos" obrigaria a inventar um
    `Protocol` para uma união que já é fechada.

    >>> validated_spell_cast(match, actor, CardInstanceId(3), None,
    ...                      catalog=catalog).spell.energy
    4
    """
    card = card_in_hand(actor, card_instance_id)
    spell = _as_spell(card, catalog)

    ensure_enough_energy(actor, card, spell.energy)
    target = _validated_target(match, actor, card, spell, target_card_instance_id)

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
    if expected is TargetKind.ALLIED_UNIT:
        return actor.user_id

    return match.opponent_of(actor.user_id).user_id
