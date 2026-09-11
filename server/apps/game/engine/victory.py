"""A §10: a única saída da partida, e a única porta que escreve Nexus.

Duas funções públicas, e a divisão entre elas é a razão de este módulo existir
separado do aplicador de efeito:

- `change_nexus` altera **um** Nexus e verifica logo em seguida. É o que a §5B
  usa: SACRIFICIAL FIRE e LIFE POTION mexem num Nexus de cada vez.
- `check_victory` só verifica. É o que a §7.3 vai usar, em que o dano de combate
  é simultâneo e altera os dois Nexus antes de existir um resultado a apurar.

O Nexus não tem teto nem piso. O 20 da §12 é o valor **inicial**, não um limite,
e a sessão de esclarecimento da feature 006 fixou que a cura pode ultrapassá-lo.
Um piso em zero apagaria por quanto o jogador passou do ponto, que é o que
distingue um empate apertado de um estouro.

Terminar a partida é escrever dois campos que precisam concordar -- o resultado
e a fase terminal. `_finish_match` é o único ponto do código que faz isso, e é a
existência desse ponto único que torna a invariante afirmável em vez de
esperançosa.
"""

from apps.game.match import Match, MatchOutcome, MatchPhase, PlayerState


def change_nexus(match: Match, player: PlayerState, amount: int) -> None:
    """Altera o Nexus de um jogador e apura a §10 em seguida.

    `amount` é assinado: LIFE POTION soma, SACRIFICIAL FIRE subtrai, e o dano
    de combate da §7.3 vai subtrair pela mesma porta.

    Sem teto e sem piso -- ver o cabeçalho do módulo.

    >>> change_nexus(match, caster, -8)
    >>> caster.nexus
    12
    """
    player.nexus += amount

    check_victory(match)


def check_victory(match: Match) -> None:
    """A §10, depois de qualquer evento que altere um Nexus.

    Nexus ≤ 0 derrota o jogador; os dois ≤ 0 no mesmo cálculo é empate.

    Idempotente: uma partida já terminada não muda de resultado, e chamar de
    novo não faz nada. É o que permite ao combate chamá-la depois do dano
    simultâneo sem contar quantas vezes já foi chamada -- e o que impede um
    efeito posterior de reescrever um desfecho já apurado.

    >>> check_victory(match)
    >>> match.is_over
    True
    """
    if match.is_over:
        return

    # A §10 escreve "Nexus <= 0", e o zero é a regra, não um valor calibrável
    # como os da §12. Por isso é literal, e não constante nomeada.
    defeated = tuple(player.user_id for player in match.players if player.nexus <= 0)

    if not defeated:
        return

    _finish_match(match, MatchOutcome(defeated_user_ids=defeated))


def _finish_match(match: Match, outcome: MatchOutcome) -> None:
    """Único ponto que escreve o par (resultado, fase terminal).

    Privado de propósito: a invariante `outcome is not None` ⟺ `phase is
    FINISHED` vale porque existe um lugar só onde ela pode ser quebrada.
    """
    match.outcome = outcome
    match.phase = MatchPhase.FINISHED
