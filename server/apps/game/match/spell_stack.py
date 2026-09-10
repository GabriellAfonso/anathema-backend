"""A pilha de feitiços pendentes: o que foi lançado e ainda não resolveu.

Resolve em LIFO (Fluxo de Partida §6). Quem resolve não é este módulo — aqui a
entrada só é representada.

O alvo é guardado como identificador, nunca como referência ao objeto. Com
referência, quem resolve aplica efeito em unidade já removida do jogo; com
identificador, dá para perguntar se ela ainda está em campo e deixar o feitiço
fizzlar quando não estiver.
"""

from dataclasses import dataclass

from .cards_in_play import CardInstanceId, MatchCard


@dataclass(slots=True)
class StackEntry:
    """Um feitiço lançado e ainda não resolvido.

    `target_card_instance_id is None` significa que o feitiço **não mira
    nada** — `RestoreNexus`, `SacrificeNexusForAttack`. Nunca significa que o
    alvo sumiu: essa é a resposta de `Match.bank_unit()`, e as duas perguntas
    não se confundem.

    >>> entry = StackEntry(spell, caster_user_id=9, target_card_instance_id=None)
    >>> entry.target_card_instance_id is None
    True
    """

    card: MatchCard
    caster_user_id: int
    target_card_instance_id: CardInstanceId | None = None
