"""A §10: a única saída da partida, e a única porta que escreve Nexus.

Duas funções públicas, e a divisão entre elas é a razão de este módulo existir
separado do aplicador de efeito:

- `change_nexus` altera **um** Nexus e verifica logo em seguida. É o que a §5B
  usa: SACRIFICIAL FIRE e LIFE POTION mexem num Nexus de cada vez.
- `change_nexus_simultaneously` altera vários e verifica **uma vez**, depois de
  todos. É o que a §7.3 usa: o dano de combate pode zerar os dois Nexus no mesmo
  cálculo, e a §10 chama isso de empate.
- `check_victory` só verifica, e é idempotente.

Escolher a primeira onde cabe a segunda é o bug que nenhum teste de um jogador
só pega: a primeira apuração já encerraria a partida com um único derrotado, e
a segunda não corrigiria nada.

O Nexus não tem teto nem piso. O 20 da §12 é o valor **inicial**, não um limite,
e a sessão de esclarecimento da feature 006 fixou que a cura pode ultrapassá-lo.
Um piso em zero apagaria por quanto o jogador passou do ponto, que é o que
distingue um empate apertado de um estouro.

Terminar a partida é escrever dois campos que precisam concordar -- o resultado
e a fase terminal. `_finish_match` é o único ponto do código que faz isso, e é a
existência desse ponto único que torna a invariante afirmável em vez de
esperançosa.
"""

from collections.abc import Sequence

from apps.game.match import Match, MatchOutcome, MatchPhase, PlayerState


def change_nexus(match: Match, player: PlayerState, amount: int) -> None:
    """Altera o Nexus de um jogador e apura a §10 em seguida.

    `amount` é assinado: LIFE POTION soma, SACRIFICIAL FIRE subtrai.

    Sem teto e sem piso -- ver o cabeçalho do módulo.

    O dano de combate **não** passa por aqui: ele altera os dois Nexus antes de
    apurar, e usa `change_nexus_simultaneously`.

    >>> change_nexus(match, caster, -8)
    >>> caster.nexus
    12
    """
    _add_to_nexus(player, amount)

    check_victory(match)


def change_nexus_simultaneously(
    match: Match, amount_by_player: Sequence[tuple[PlayerState, int]]
) -> None:
    """Altera vários Nexus e apura a §10 **uma vez**, depois de todos (§7.3).

    É a porta do dano de combate, e a diferença entre ela e `change_nexus` é a
    razão de `check_victory` existir separada desde a feature 006: apurar depois
    de cada alteração transformaria o empate da §10 em vitória do segundo,
    porque a primeira apuração já encerraria a partida com um único derrotado e
    a verificação é idempotente.

    O combate cita os **dois** jogadores sempre, inclusive o atacante com 0 --
    a soma de 0 não é operação morta, é a afirmação de que ele participou do
    mesmo cálculo.

    >>> change_nexus_simultaneously(match, ((defender, -7), (attacker, 0)))
    """
    for player, amount in amount_by_player:
        _add_to_nexus(player, amount)

    check_victory(match)


def _add_to_nexus(player: PlayerState, amount: int) -> None:
    """Único ponto do código que escreve Nexus.

    Privado pela mesma razão de `_finish_match`: as duas portas públicas
    diferem só em **quando** apuram, e um ponto só de escrita é o que impede uma
    terceira de aparecer sem passar pela §10.
    """
    player.nexus += amount


def check_victory(match: Match) -> None:
    """A §10, depois de qualquer evento que altere um Nexus.

    Nexus ≤ 0 derrota o jogador; os dois ≤ 0 no mesmo cálculo é empate.

    Idempotente: uma partida já terminada não muda de resultado, e chamar de
    novo não faz nada. É o que impede um efeito posterior de reescrever um
    desfecho já apurado -- e é também o que torna a escolha errada entre as duas
    portas **silenciosa**, porque a segunda apuração não desfaz a primeira.

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
