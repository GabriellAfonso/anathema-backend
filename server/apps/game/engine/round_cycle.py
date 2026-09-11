"""As duas portas do ciclo de rodada, e a cascata que mantém a partida girando.

`begin_round_cycle` é o primeiro empurrão: o setup da §3 entrega a partida
montada e parada em `UPKEEP`, sem tê-lo executado -- posicionar não é executar --
e isto executa. Roda uma vez por partida.

`submit_action` é a porta por onde toda jogada entra, e ela devolve a partida
**já estabilizada**: nunca em `UPKEEP`, nunca em `ROUND_END`. Um único "passar"
pode disparar a cascata inteira -- fim de rodada, varredura, troca de token,
rodada +1, e o Upkeep da rodada seguinte com energia e compra dos dois -- e o
chamador lê o resultado disso, não um estado intermediário.

Executar um passo por chamada e devolver a partida em `ROUND_END` satisfaria
cada regra isolada e travaria na primeira partida real. Por isso a cascata é um
laço, e não uma sequência fixa de chamadas: quem decide a próxima fase é a saída
da §5, e o laço atravessa o que estiver lá.
"""

from typing import assert_never

from apps.game.cards import CardCatalog
from apps.game.match import Match, MatchPhase, PlayerState
from apps.game.randomness import RandomSource

from .blocker_pairing import assign_blocker, remove_blocker
from .cast_spell import cast_spell
from .combat_cleanup import end_combat
from .declare_attack import confirm_attack, declare_attack, withdraw_attacker
from .play_unit import play_unit
from .combat_action import (
    AssignBlockerAction,
    ConfirmAttackAction,
    EndDefenseWindowAction,
    RemoveBlockerAction,
    WithdrawAttackerAction,
)
from .player_action import (
    CastSpellAction,
    DeclareAttackAction,
    PassAction,
    PlayerAction,
    PlayUnitAction,
    ensure_action_allowed,
)
from .round_end import end_round
from .upkeep import run_upkeep

# Fluxo de Partida §5, "Saída da fase". Dois, e não "todos os jogadores
# passaram": como a prioridade troca a cada ação, dois passes consecutivos já
# significam que os dois passaram, nunca que um passou duas vezes.
CONSECUTIVE_PASSES_TO_EXIT = 2


class MatchNotAwaitingUpkeepError(Exception):
    """Pediram o primeiro empurrão numa partida que não está parada antes do
    Upkeep. Cita a fase atual.

    Cobre os dois casos: a partida ainda em mulligan, e a partida que já foi
    iniciada -- o Upkeep da Rodada 1 roda uma vez só.

    >>> raise MatchNotAwaitingUpkeepError(MatchPhase.ACTION, "m-1")
    MatchNotAwaitingUpkeepError: match 'm-1' is in phase 'action': expected
    'upkeep' to begin the round cycle
    """

    def __init__(self, phase: MatchPhase, match_id: str) -> None:
        super().__init__(
            f"match {match_id!r} is in phase '{phase}': "
            f"expected '{MatchPhase.UPKEEP}' to begin the round cycle"
        )
        self.phase = phase
        self.match_id = match_id


def begin_round_cycle(match: Match, *, randomness: RandomSource) -> None:
    """O Upkeep da Rodada 1 que o setup deixou pendente.

    Depois dela a partida só para esperando ação de jogador: todo Upkeep
    seguinte acontece dentro da cascata de `submit_action`, e nenhum outro
    empurrão é necessário.

    Altera `match` no lugar, como `record_mulligan` e `finish_setup`. Quem grava
    é o chamador, pelo caminho atômico da feature 003.

    >>> begin_round_cycle(match, randomness=source)
    >>> match.phase
    <MatchPhase.ACTION: 'action'>
    """
    if match.phase is not MatchPhase.UPKEEP:
        raise MatchNotAwaitingUpkeepError(match.phase, match.match_id)

    run_upkeep(match, randomness=randomness)


def submit_action(
    match: Match,
    action: PlayerAction,
    *,
    catalog: CardCatalog,
    randomness: RandomSource,
) -> None:
    """Uma ação de jogador, e a partida de volta ao ponto de esperar ação.

    Quatro passos, nesta ordem: as três guardas comuns da §5, a regra específica
    da ação, a troca de prioridade, e a saída da fase com a cascata que a
    atravessa.

    Recusa levanta e não muta: nenhuma regra escreve antes de todas as suas
    guardas passarem, então não há meia ação a desfazer.

    `catalog` é exigido mesmo por um passe, que não o usa: a porta é uma só, e
    recebe o que a mais cara das ações precisa.

    >>> submit_action(match, PassAction(actor_user_id=7),
    ...               catalog=catalog, randomness=source)
    >>> match.consecutive_passes
    1
    """
    actor = ensure_action_allowed(match, action)

    _apply_action(match, actor, action, catalog)

    _pass_priority(match, action)
    _exit_action_phase(match)
    _settle(match, randomness)


def _apply_action(
    match: Match, actor: PlayerState, action: PlayerAction, catalog: CardCatalog
) -> None:
    """A regra específica de cada braço da união.

    `match` sobre a união fechada: um braço novo sem regra escrita é erro de
    mypy, não jogada que some em produção.

    O `assert_never` é o que torna a exaustividade **verificada**. Um `match`
    que devolve `None` não obriga o mypy a cobrir a união sozinho, ao contrário
    de `to_modifier_document`, que devolve valor -- é o mesmo buraco que a
    feature 006 encontrou em `spell_effect._dispatch`, e a mesma solução.
    """
    match action:
        case PlayUnitAction():
            play_unit(match, actor, action, catalog=catalog)
        case CastSpellAction():
            cast_spell(match, actor, action, catalog=catalog)
        case DeclareAttackAction():
            declare_attack(match, actor, action)
        case WithdrawAttackerAction():
            withdraw_attacker(match, action)
        case ConfirmAttackAction():
            confirm_attack(match)
        case AssignBlockerAction():
            assign_blocker(match, actor, action)
        case RemoveBlockerAction():
            remove_blocker(match, action)
        case EndDefenseWindowAction():
            end_combat(match, catalog=catalog)
        case PassAction():
            _pass_turn(match)
        case _:
            assert_never(action)


def _pass_turn(match: Match) -> None:
    """A §5D inteira. Não toca zona de carta, energia, Nexus nem modificador."""
    match.consecutive_passes += 1


def _pass_priority(match: Match, action: PlayerAction) -> None:
    """A prioridade passa ao oponente do autor, depois da ação que gasta a vez.

    Usa `action.actor_user_id` em vez de `match.priority_user_id` porque a
    guarda comum já provou que os dois são o mesmo -- e este é um `int`, não um
    `int | None`.

    O `return` são as exceções à alternância: jogar feitiço, que não gasta a
    vez em fase nenhuma (§5B), e as janelas do combate, em que o atacante monta
    a zona de ataque (§7.1) e o defensor bloqueia (§7.2) quantas vezes quiserem.
    As exceções são propriedade **da ação**, como `allowed_phases` já é, e é por
    isso que não vazam -- jogar unidade, passar e confirmar o ataque declaram
    `keeps_priority = False` cada um por si.
    """
    if action.keeps_priority:
        return

    match.priority_user_id = match.opponent_of(action.actor_user_id).user_id


def _exit_action_phase(match: Match) -> None:
    """A saída da §5, verificada depois de toda ação: dois passes seguidos
    fecham a rodada.

    Um ramo só. Até a feature 008 havia um segundo, que mandava a partida
    resolver os feitiços pendentes antes; com o feitiço resolvendo na hora em
    que é jogado, não sobra nada pendente, e dois passes são sempre Fim de
    Rodada. Fora da Fase de Ação ninguém passa, e os passes ficam em 0 -- é isso
    que deixa esta função inerte durante o combate.
    """
    if match.consecutive_passes < CONSECUTIVE_PASSES_TO_EXIT:
        return

    match.phase = MatchPhase.ROUND_END


def _settle(match: Match, randomness: RandomSource) -> None:
    """Atravessa toda fase automática até a partida voltar a esperar ação.

    Laço, e não uma sequência fixa de chamadas: a saída da §5 é quem decide qual
    fase vem, e o laço atravessa o que estiver lá. A feature 006 acrescentou um
    braço aqui e a 008 o tirou, sem que o laço mudasse de forma -- que era o que
    a feature 005 previu ao escrevê-lo assim.

    Termina sempre, em no máximo uma volta completa: `ROUND_END` leva a
    `UPKEEP`, e `UPKEEP` leva a `ACTION`.

    `FINISHED` não está entre as automáticas, então a partida encerrada para o
    laço sem que ele precise saber da §10.
    """
    while match.phase in _AUTOMATIC_PHASES:
        _run_automatic_phase(match, randomness)


def _run_automatic_phase(match: Match, randomness: RandomSource) -> None:
    """Um passo da cascata. Cada fase automática sabe para onde vai."""
    if match.phase is MatchPhase.ROUND_END:
        end_round(match)
        return

    run_upkeep(match, randomness=randomness)


_AUTOMATIC_PHASES = frozenset({MatchPhase.ROUND_END, MatchPhase.UPKEEP})
