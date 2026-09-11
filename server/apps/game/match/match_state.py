"""Uma partida viva entre dois jogadores, endereçada por `match_id`.

Construída por `apps.game.engine.start_match` e gravada pelo `MatchStore`,
nunca montada à mão num consumer: montar a partida é a §3, e o estado precisa
chegar ao Redis para os outros workers do uvicorn enxergarem a partida.

Este módulo guarda o estado e responde perguntas sobre ele. Nada aqui decide
se uma jogada é legal, aplica dano, troca prioridade ou avança fase — isso é
regra, e regra é do motor.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from apps.game.randomness import RandomSeed, Roll

from .cards_in_play import BankUnit, CardInstanceId
from .combat_state import CombatState
from .match_outcome import MatchOutcome
from .player_state import PlayerState


class MatchPhase(StrEnum):
    """As cinco fases da §2, mais a espera do setup. Conjunto fechado.

    A §2 lista cinco porque descreve o ciclo de uma rodada. `MULLIGAN` não é
    uma sexta fase do ciclo: é o momento da §3, antes da Rodada 1, em que a
    partida já existe e já está gravada e o setup espera os dois jogadores
    decidirem. Uma partida sai dela quando o segundo responde e nunca volta.

    `DECLARATION` e `COMBAT` são as duas janelas da §7, e as únicas fases que
    **esperam** jogador além da Fase de Ação. Por isso estão fora do conjunto de
    fases automáticas da cascata. Na primeira a partida espera o atacante montar
    a zona de ataque, e sai dela por **Atacar** ou puxando todos de volta; na
    segunda espera o defensor, e sai por **Resolver**. Nas duas a prioridade
    não troca enquanto se age na janela — ver `keeps_priority` em
    `engine/player_action.py` —, e o que as duas precisam mora em
    `Match.combat`.

    `DECLARATION` entrou com a correção da nota de 2026-09-11: até então
    declarar ataque era uma ação só, que consumia o token e ia direto à defesa.

    `FINISHED` também não é fase do ciclo: é o outro lado da partida, o da §10.
    É **terminal** — nenhuma transição sai dela — e está fora de
    `allowed_phases` de toda ação e fora do conjunto de fases automáticas da
    cascata. As duas ausências são o que faz a partida terminada recusar
    qualquer jogada e parar a cascata sem uma linha escrita para isso.
    """

    MULLIGAN = "mulligan"
    UPKEEP = "upkeep"
    ACTION = "action"
    DECLARATION = "declaration"
    COMBAT = "combat"
    ROUND_END = "round_end"
    FINISHED = "finished"


class NotAParticipantError(Exception):
    """Pediram o estado de um `user_id` que não joga esta partida.

    É erro de programação, não fluxo normal: o gate de `MatchConsumer` já
    deveria ter fechado o socket. Quem quer só perguntar usa `has_player`.
    """

    def __init__(self, user_id: int | None, match_id: str) -> None:
        super().__init__(
            f"user {user_id} does not play match {match_id!r}: "
            f"expected the user_id of one of its two players"
        )
        self.user_id = user_id
        self.match_id = match_id


class MatchIsNotInCombatError(Exception):
    """Pediram o combate de uma partida que não está em combate.

    É erro de programação, não fluxo normal: as regras da §7.2 e da §7.3 só
    são alcançáveis de `MatchPhase.COMBAT`, e a guarda de fase já provou isso
    antes de qualquer uma delas perguntar.

    Não herda de `IllegalActionError` pela mesma razão que
    `NotAParticipantError` não herda: ela mora aqui, e herdar inverteria a
    dependência entre o pacote de estado e o de regra.

    >>> raise MatchIsNotInCombatError(MatchPhase.ACTION, "m-1")
    MatchIsNotInCombatError: match 'm-1' is in phase 'action': expected
    'combat' to have a combat in progress
    """

    def __init__(self, phase: MatchPhase, match_id: str) -> None:
        super().__init__(
            f"match {match_id!r} is in phase '{phase}': "
            f"expected '{MatchPhase.COMBAT}' to have a combat in progress"
        )
        self.phase = phase
        self.match_id = match_id


@dataclass(slots=True)
class Match:
    """A partida inteira: os dois jogadores e tudo que a §2 lista.

    >>> match = start_match(one, two, catalog=catalog, randomness=src, seed=s)
    >>> match.phase
    <MatchPhase.MULLIGAN: 'mulligan'>
    """

    match_id: str
    # Tupla de dois, não lista: a aridade fica no tipo, e o mypy recusa uma
    # partida com um ou três jogadores. Nenhuma estrutura daqui é indexada por
    # `user_id` -- chave de objeto JSON é sempre string, e o modelo anterior
    # só sobrevivia porque convertia de volta na leitura. Sem chave, não sobra
    # o que converter.
    players: tuple[PlayerState, PlayerState]
    # A semente de onde sai toda a aleatoriedade desta partida. Nasce na
    # criação e não muda. Fica no estado, e não num gerador de processo, porque
    # o mulligan e o sorteio do token acontecem depois de a partida ir ao Redis
    # e voltar -- possivelmente em outro worker, que precisa continuar a mesma
    # sequência.
    random_seed: RandomSeed
    # `None` até o sorteio da §3, os dois juntos. Não é valor de espera: no
    # meio do setup não existe dono do token, e afirmar um seria mentir num
    # campo que ninguém checa.
    token_holder_user_id: int | None = None
    priority_user_id: int | None = None
    round_number: int = 1
    token_consumed: bool = False
    phase: MatchPhase = MatchPhase.MULLIGAN
    # `None` é partida em andamento (§10). Não é valor de espera: enquanto
    # ninguém chegou a Nexus 0 não existe desfecho, e afirmar um seria mentir.
    #
    # Anda sempre junto de `phase is FINISHED`, e um ponto só do código escreve
    # o par -- `_finish_match`, em `engine/victory.py`. Os dois campos existem
    # porque respondem perguntas com consumidores diferentes: a fase é o que a
    # cascata lê para parar e o que `allowed_phases` compara para recusar; isto
    # é quem perdeu, que a fase não sabe dizer e não deveria.
    outcome: MatchOutcome | None = None
    # `None` é "não há combate", e não valor de espera: fora da §7 não existe
    # pareamento, e um `CombatState` vazio permanente confundiria "ninguém
    # bloqueou" com "ninguém atacou".
    #
    # Anda junto de `phase is COMBAT`, mas só numa direção: uma partida que
    # acaba **dentro** da janela do defensor fica em `FINISHED` com o combate
    # intacto, e é esse estado congelado que registra que o combate foi
    # interrompido em vez de resolvido.
    combat: CombatState | None = None
    consecutive_passes: int = 0
    # Contador de identidade de carta. Campo do estado, e não do processo,
    # porque a partida é lida por qualquer worker do uvicorn: um contador de
    # processo daria números repetidos entre workers.
    next_card_instance_id: int = 1
    # Contador de sorteios, pelo mesmo motivo do contador de cartas: um
    # contador de processo daria números repetidos entre workers. Cada sorteio
    # abre um fluxo próprio a partir de `(random_seed, ordinal)`, então quantos
    # números uma operação consome não afeta a seguinte.
    next_roll_ordinal: int = 1

    def mint_roll(self) -> Roll:
        """Cunha o próximo sorteio desta partida.

        Único ponto do código que produz um `Roll`, como
        `mint_card_instance_id` é o único que produz identidade de carta.
        Dois sorteios da mesma partida nunca compartilham o ordinal, e é isso
        que impede duas operações de consumirem o mesmo fluxo.

        >>> match.mint_roll().ordinal
        1
        """
        minted = self.next_roll_ordinal
        self.next_roll_ordinal += 1

        return Roll(seed=self.random_seed, ordinal=minted)

    @property
    def is_over(self) -> bool:
        """A partida acabou (§10). Derivada de `outcome`, nunca gravada.

        Um booleano gravado ao lado do resultado poderia discordar dele, que é
        o mesmo argumento de `awaiting_mulligan_user_ids` logo abaixo.

        >>> match.is_over
        False
        """
        return self.outcome is not None

    @property
    def awaiting_mulligan_user_ids(self) -> tuple[int, ...]:
        """De quem o setup ainda espera. Vazia = pronto para o sorteio do token.

        Derivada de `mulligan_taken`, nunca gravada: uma segunda lista a manter
        em sincronia não daria erro quando alguém esquecesse de atualizá-la --
        daria espera eterna, que é pior.

        >>> match.awaiting_mulligan_user_ids
        (7, 9)
        """
        return tuple(
            player.user_id for player in self.players if not player.mulligan_taken
        )

    def has_player(self, user_id: int | None) -> bool:
        """A partida é o dono da regra de quem pode falar com ela.

        Aceita `None` e devolve `False`: um socket sem usuário autenticado
        nunca passa no gate, e nunca levanta.

        >>> match.has_player(7)
        True
        """
        return any(player.user_id == user_id for player in self.players)

    def player(self, user_id: int) -> PlayerState:
        """O estado do jogador, ou recusa citando o `user_id` pedido.

        >>> match.player(7).nexus
        20
        """
        for player in self.players:
            if player.user_id == user_id:
                return player

        raise NotAParticipantError(user_id, self.match_id)

    def opponent_of(self, user_id: int) -> PlayerState:
        """O outro jogador, ou recusa citando o `user_id` pedido.

        >>> match.opponent_of(7).user_id
        9
        """
        first, second = self.players

        if first.user_id == user_id:
            return second

        if second.user_id == user_id:
            return first

        raise NotAParticipantError(user_id, self.match_id)

    def bank_unit(self, card_instance_id: CardInstanceId) -> BankUnit | None:
        """A unidade em campo com aquele identificador, ou `None`.

        `None` **não é erro**: é a resposta que torna o bloqueador órfão da
        §7.3 possível de perguntar -- o atacante que um feitiço do defensor
        matou não está mais em campo. Quem pergunta não precisa saber de qual
        jogador a unidade é, nem envolver a chamada em `try`.

        Diverge de `player()`, que levanta, porque as perguntas são
        diferentes: pedir um jogador que não joga é bug; perguntar por uma
        unidade que saiu de campo é o caso normal.

        >>> match.bank_unit(CardInstanceId(3)) is None
        True
        """
        for player in self.players:
            found = _unit_in_bank(player.bank, card_instance_id)

            if found is not None:
                return found

        return None

    def ongoing_combat(self) -> CombatState:
        """O combate em curso, ou recusa citando a fase.

        Mesma forma e mesma razão de `player()`: perguntar por um combate que
        não existe é bug de chamador, e as três regras da §7 que precisam do
        estreitamento escreveriam a mesma recusa três vezes se ele não morasse
        aqui.

        Diverge de `bank_unit()`, que devolve `None`, porque as perguntas são
        diferentes: um alvo que sumiu é o caso normal da §6; uma partida fora
        do combate chegando à §7.2 não é.

        >>> match.ongoing_combat().attacker_card_instance_ids
        [3, 5]
        """
        if self.combat is None:
            raise MatchIsNotInCombatError(self.phase, self.match_id)

        return self.combat

    def mint_card_instance_id(self) -> CardInstanceId:
        """Cunha o próximo identificador de carta desta partida.

        Único ponto do código que produz um `CardInstanceId`. **Não** é
        chamado ao mover carta de zona: o identificador nasce com a carta e
        acompanha ela, e o reset de deck da §9 devolve as mesmas cartas com os
        mesmos números.

        >>> match.mint_card_instance_id()
        1
        """
        minted = self.next_card_instance_id
        self.next_card_instance_id += 1

        return CardInstanceId(minted)


def _unit_in_bank(
    bank: Sequence[BankUnit], card_instance_id: CardInstanceId
) -> BankUnit | None:
    """Busca num banco só. Extraída para manter `bank_unit` em dois níveis."""
    for unit in bank:
        if unit.card.card_instance_id == card_instance_id:
            return unit

    return None
