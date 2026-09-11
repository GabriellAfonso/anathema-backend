"""A ação B da §5: lançar um feitiço da mão, pela pilha.

As quatro guardas do lançamento moram em `spell_cast_guards.py`, porque a §7.2
faz as mesmas na mesma ordem. O que é **desta** ação é o que acontece depois
delas: descontar a energia, tirar a carta da mão, e empilhar.

**O efeito não acontece aqui.** O feitiço vai para o topo da pilha e resolve
depois, quando os dois jogadores passarem (§6). É essa espera que dá ao oponente
a chance de responder, e é a única diferença entre esta ação e a §5A -- e entre
ela e o feitiço imediato da §7.2, que resolve na hora e não dá resposta nenhuma.

A entrada da pilha guarda o **identificador** do alvo, e não o `BankUnit` que a
guarda já resolveu: entre o lançamento e a resolução o alvo pode sumir, e é a
revalidação por identificador que torna o fizzle possível. O
`ValidatedSpellCast.target` é descartado aqui de propósito.
"""

from apps.game.cards import CardCatalog
from apps.game.match import Match, PlayerState, StackEntry

from .player_action import CastSpellAction
from .spell_cast_guards import validated_spell_cast


def cast_spell(
    match: Match,
    actor: PlayerState,
    action: CastSpellAction,
    *,
    catalog: CardCatalog,
) -> None:
    """A §5B: desconta a energia, tira a carta da mão, empilha o feitiço.

    Recebe o `actor` que `ensure_action_allowed` já buscou, como `play_unit`.

    Zera a contagem de passes, inclusive quando o oponente já tinha passado uma
    vez: a §5 conta passes **consecutivos**, e uma jogada quebra a sequência.

    A prioridade **não** é trocada aqui -- quem troca é `submit_action`, depois
    de toda ação. É essa troca que dá ao oponente a chance de responder no topo.

    >>> cast_spell(match, actor, action, catalog=catalog)
    >>> match.stack[-1].caster_user_id
    7
    """
    validated = validated_spell_cast(
        match,
        actor,
        action.card_instance_id,
        action.target_card_instance_id,
        catalog=catalog,
    )

    actor.energy_current -= validated.spell.energy
    actor.hand.remove(validated.card)
    match.stack.append(
        StackEntry(
            card=validated.card,
            caster_user_id=actor.user_id,
            target_card_instance_id=action.target_card_instance_id,
        )
    )
    match.consecutive_passes = 0
