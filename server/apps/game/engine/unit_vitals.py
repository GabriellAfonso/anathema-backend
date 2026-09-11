"""As perguntas sobre uma unidade em campo: quanta vida ela tem e se o dano
entra nela.

Só consulta. Nada aqui altera unidade, banco ou partida -- quem altera é
`unit_damage.py`, e a separação é a razão de mudar de cada um: estas contas
mudam quando a fórmula de vida ou de ataque mudar (uma palavra-chave da §13), e
aquela muda quando o efeito do dano mudar. O combate da §7 entrou sem tocar
`unit_damage.py`, e acrescentou uma conta aqui -- que é a prova de que a
separação estava no lugar certo.

`BankUnit.damage_taken` diz de si mesmo que a conta de vida é do motor. Este é o
motor chegando ao lugar que aquele texto reservou.

**Duas quantidades, dois nomes.** A spec da feature 006 usa "vida efetiva" com
dois sentidos -- em FR-034 subtrai o dano, em FR-044 não --, e as duas leituras
são a mesma desigualdade escrita de dois jeitos:

    dano >= máxima   <=>   máxima - dano <= 0   <=>   restante <= 0

Nomear as duas evita que o leitor precise adivinhar qual delas o nome significa
naquela linha.

`unit_effective_attack` mora aqui desde o combate. SACRIFICIAL FIRE escreve o
modificador de ataque desde a feature 006, e quem o **lê** é a §7.3 -- os dois
lados de um par e o dano que chega ao Nexus saem dela.
"""

from apps.game.cards import CardCatalog, CardType, Unit
from apps.game.match import AttackModifier, BankUnit, DamageImmunity, HealthModifier


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


def unit_effective_attack(unit: BankUnit, *, catalog: CardCatalog) -> int:
    """O ataque do molde mais a soma dos modificadores de ataque, com piso em 0.

    É a quantidade que a §7.3 usa nos dois lados de um par e no dano que chega
    ao Nexus. Dano acumulado **não** entra: uma unidade machucada bate igual.

    O piso existe porque `AttackModifier` aceita `amount` negativo por
    construção -- o docstring dele diz "negativo é como se reduz ataque" -- e
    nenhuma das cinco cartas do MVP produz um. Sem o piso, um ataque negativo
    **curaria**: `deal_damage_to_unit` reduziria `damage_taken`, e o Nexus
    subiria. Nenhuma das duas é regra da §7.

    O piso mora aqui e não em `deal_damage_to_unit`: aquele módulo também serve
    SUMMONED AX, cujo `amount` é positivo por construção, e pôr o piso lá
    escreveria uma regra da §7.3 no caminho da §5B.

    >>> unit_effective_attack(unit, catalog=catalog)   # molde 3, +3 do FIRE
    6
    """
    template = _template_of(unit, catalog)
    bonus = sum(
        modifier.amount
        for modifier in unit.modifiers
        if isinstance(modifier, AttackModifier)
    )

    return max(0, template.attack + bonus)


def unit_has_damage_immunity(unit: BankUnit) -> bool:
    """Se há um `DamageImmunity` ativo na unidade (MAGIC BARRIER).

    Sem `catalog`: imunidade é da instância, nunca do molde.

    Mora entre as consultas e não entre as alterações porque é pergunta. Quem a
    faz é `deal_damage_to_unit`, e é por isso que o combate da §7.3 herdou a
    imunidade sem uma linha escrita para ela: o dano de combate entra pela mesma
    porta que o de feitiço.

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
