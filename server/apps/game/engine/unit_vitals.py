"""As perguntas sobre uma unidade em campo: quanta vida ela tem e se o dano
entra nela.

Só consulta. Nada aqui altera unidade, banco ou partida -- quem altera é
`unit_damage.py`, e a separação é a razão de mudar de cada um: esta conta muda
quando a fórmula de vida mudar (uma palavra-chave da §13), e aquela muda quando
o efeito do dano mudar (o combate da §7).

`BankUnit.damage_taken` diz de si mesmo que a conta de vida é do motor. Este é o
motor chegando ao lugar que aquele texto reservou.

**Duas quantidades, dois nomes.** A spec da feature 006 usa "vida efetiva" com
dois sentidos -- em FR-034 subtrai o dano, em FR-044 não --, e as duas leituras
são a mesma desigualdade escrita de dois jeitos:

    dano >= máxima   <=>   máxima - dano <= 0   <=>   restante <= 0

Nomear as duas evita que o leitor precise adivinhar qual delas o nome significa
naquela linha.

`unit_effective_attack` **não mora aqui ainda**: SACRIFICIAL FIRE escreve o
modificador de ataque, e quem lê ataque é a §7.3. Ela entra com o combate, junto
das regras de bloqueio que só ele conhece.
"""

from apps.game.cards import CardCatalog, CardType, Unit
from apps.game.match import BankUnit, DamageImmunity, HealthModifier


class BankUnitIsNotAUnitError(Exception):
    """O molde de uma carta em banco não é uma unidade.

    Estado corrompido, não jogada: só unidade entra no banco, e `play_unit` já
    provou isso ao pô-la lá. Recusa nomeada em vez de `assert` -- que some com
    `-O` -- e em vez de `cast`, que calaria o mypy sem responder a pergunta.

    >>> raise BankUnitIsNotAUnitError(CardInstanceId(3), CardId(1001), CardType.SPELL)
    BankUnitIsNotAUnitError: card instance 3 (card 1001) in a bank is a spell:
    expected a unit
    """

    def __init__(self, unit: BankUnit, card_type: CardType) -> None:
        super().__init__(
            f"card instance {unit.card.card_instance_id} "
            f"(card {unit.card.card_id}) in a bank is a {card_type}: "
            f"expected a unit"
        )
        self.card_instance_id = unit.card.card_instance_id
        self.card_type = card_type


def unit_max_health(unit: BankUnit, *, catalog: CardCatalog) -> int:
    """A vida do molde mais a soma dos modificadores de vida.

    É esta a quantidade que a morte compara, e é o que a spec chama de "vida
    efetiva" em FR-044 e nos cenários dos cinco efeitos.

    >>> unit_max_health(unit, catalog=catalog)   # molde 4, +2 de SOMEONE'S SHIELD
    6
    """
    template = _template_of(unit, catalog)
    bonus = sum(
        modifier.amount
        for modifier in unit.modifiers
        if isinstance(modifier, HealthModifier)
    )

    return template.health + bonus


def unit_remaining_health(unit: BankUnit, *, catalog: CardCatalog) -> int:
    """A máxima menos o dano acumulado. É a "vida efetiva" de FR-034.

    Pode ser zero ou negativa: a unidade morta é removida pela varredura de
    `unit_damage.bury_dead_units`, não por esta conta.

    >>> unit_remaining_health(unit, catalog=catalog)   # máxima 6, 3 de dano
    3
    """
    return unit_max_health(unit, catalog=catalog) - unit.damage_taken


def unit_is_dead(unit: BankUnit, *, catalog: CardCatalog) -> bool:
    """O dano acumulado alcançou a vida máxima (§7.4).

    Escrita sobre a restante, e não sobre a máxima, porque as duas formas são a
    mesma desigualdade e esta dispensa repetir `damage_taken` na comparação.

    >>> unit_is_dead(unit, catalog=catalog)
    False
    """
    return unit_remaining_health(unit, catalog=catalog) <= 0


def unit_has_damage_immunity(unit: BankUnit) -> bool:
    """Se há um `DamageImmunity` ativo na unidade (MAGIC BARRIER).

    Sem `catalog`: imunidade é da instância, nunca do molde.

    Mora entre as consultas e não entre as alterações porque é pergunta -- o
    combate vai fazê-la sem causar dano nenhum, ao decidir bloqueio.

    >>> unit_has_damage_immunity(unit)
    True
    """
    return any(isinstance(modifier, DamageImmunity) for modifier in unit.modifiers)


def _template_of(unit: BankUnit, catalog: CardCatalog) -> Unit:
    """O molde da carta, estreitado para `Unit`.

    `isinstance` e não comparação de faixa de `card_id`: a faixa é convenção de
    alocação, e `cards/card.py` proíbe derivar tipo dela.
    """
    template = catalog.card(unit.card.card_id)

    if not isinstance(template, Unit):
        raise BankUnitIsNotAUnitError(unit, template.card_type)

    return template
