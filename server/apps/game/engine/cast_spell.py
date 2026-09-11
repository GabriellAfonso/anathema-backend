"""A ação B da §5: jogar um feitiço da mão, e o efeito **agora**.

Fluxo de Partida, corrigido em 2026-09-11: o feitiço resolve na hora em que é
jogado, em qualquer fase em que o jogador tem a prioridade -- a Fase de Ação e a
janela do defensor da §7.2 --, e não gasta a vez. Este módulo é o único caminho
de lançamento das duas fases.

As guardas moram em `spell_cast_guards.py` e o aplicador em `spell_effect.py`, e
nenhum dos dois recebe parâmetro dizendo de que fase a chamada veio. É essa
ausência que impede os cinco efeitos de terem uma segunda implementação a manter
igual à mão.

Um feitiço aceito sempre faz efeito: não há intervalo entre validar o alvo e
aplicá-lo. Alvo fora de campo é recusa da guarda, sempre.

A prioridade não é devolvida, e não é este módulo que decide isso:
`CastSpellAction.keeps_priority` é `True`, e quem lê é `round_cycle`.
"""

from apps.game.cards import CardCatalog
from apps.game.match import Match, PlayerState

from .player_action import CastSpellAction
from .spell_cast_guards import validated_spell_cast
from .spell_effect import apply_spell_effect


def cast_spell(
    match: Match,
    actor: PlayerState,
    action: CastSpellAction,
    *,
    catalog: CardCatalog,
) -> None:
    """A §5B: desconta a energia, tira a carta da mão, aplica o efeito e manda a
    carta ao cemitério.

    O cemitério vem **depois** do efeito, e não antes: uma unidade morta pelo
    efeito entra no cemitério antes da carta do feitiço. É a ordem que a feature
    007 fixou para o feitiço da janela do defensor, e a que os dois lados de
    `test_both_phases_give_the_same_state` comparam.

    Zera a contagem de passes nas duas fases. Na janela do defensor ela já está
    em 0 -- a declaração zerou e a limpeza da §7.4 zera de novo --, e escrever
    a zeragem sem condição evita um `if` de fase, que seria o primeiro passo
    para os dois lados divergirem. Na Fase de Ação é o que garante que um passe
    depois do feitiço não feche a rodada sem o oponente receber a vez.

    >>> cast_spell(match, actor, action, catalog=catalog)
    >>> match.consecutive_passes
    0
    """
    validated = validated_spell_cast(match, actor, action, catalog=catalog)

    actor.energy_current -= validated.spell.energy
    actor.hand.remove(validated.card)
    apply_spell_effect(
        match, actor, validated.spell.effect, validated.target, catalog=catalog
    )
    actor.graveyard.append(validated.card)
    match.consecutive_passes = 0
