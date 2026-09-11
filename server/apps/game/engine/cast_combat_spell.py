"""O feitiço do defensor na janela da §7.2: as mesmas guardas, e o efeito
**agora**.

É o mesmo efeito, com o mesmo resultado, do caminho da §5B -- por um caminho
diferente. As guardas são as de `spell_cast_guards.py` e o aplicador é o de
`spell_effect.py`, e nenhum dos dois recebe parâmetro dizendo de onde a chamada
veio. É essa ausência que impede os cinco efeitos de terem uma segunda
implementação a manter igual à mão.

Três diferenças para a §5B, e todas saem da mesma frase da nota -- "resolve na
hora, sem pilha, e o atacante não pode responder":

    1. o efeito acontece dentro desta chamada
    2. a carta não passa pela pilha: da mão vai direto ao cemitério
    3. **nunca fizzla**, porque não existe intervalo entre validar o alvo e
       aplicá-lo. Alvo fora de campo aqui é recusa, não fizzle.

A prioridade não é devolvida, e não é este módulo que decide isso:
`CastCombatSpellAction.keeps_priority` é `True`, e quem lê é `round_cycle`.
"""

from apps.game.cards import CardCatalog
from apps.game.match import Match, PlayerState

from .combat_action import CastCombatSpellAction
from .spell_cast_guards import validated_spell_cast
from .spell_effect import apply_spell_effect


def cast_combat_spell(
    match: Match,
    actor: PlayerState,
    action: CastCombatSpellAction,
    *,
    catalog: CardCatalog,
) -> None:
    """A §7.2: desconta a energia, tira a carta da mão e aplica o efeito.

    O cemitério vem **depois** do efeito, e não antes. É a ordem de
    `stack_resolution._resolve_top`, e o combate a copia porque os dois caminhos
    precisam dar o mesmo resultado campo a campo: uma unidade morta pelo efeito
    entra no cemitério antes da carta do feitiço, e enterrar a carta primeiro
    inverteria a ordem de um dos dois lados.

    Não zera a contagem de passes: ela já está em 0 desde a declaração, e a
    limpeza da §7.4 a zera de novo.

    >>> cast_combat_spell(match, defender, action, catalog=catalog)
    >>> match.stack
    []
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
    apply_spell_effect(
        match, actor, validated.spell.effect, validated.target, catalog=catalog
    )
    actor.graveyard.append(validated.card)
