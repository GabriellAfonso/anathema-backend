"""Uma partida viva entre dois jogadores, endereçada por `match_id`.

Construída por `apps.game.engine.start_match` e gravada pelo `MatchStore`,
nunca montada à mão num consumer: montar a partida é a §3, e o estado precisa
chegar ao Redis para os outros workers do uvicorn enxergarem a partida.

Este módulo guarda o estado e responde perguntas sobre ele. Nada aqui decide
se uma jogada é legal, aplica dano, troca prioridade ou avança fase — isso é
regra, e regra é do motor.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from apps.game.randomness import RandomSeed, Roll

from .cards_in_play import BankUnit, CardInstanceId
from .match_outcome import MatchOutcome
from .player_state import PlayerState
from .spell_stack import StackEntry


class MatchPhase(StrEnum):
    """As cinco fases da §2, mais a espera do setup. Conjunto fechado.

    A §2 lista cinco porque descreve o ciclo de uma rodada. `MULLIGAN` não é
    uma sexta fase do ciclo: é o momento da §3, antes da Rodada 1, em que a
    partida já existe e já está gravada e o setup espera os dois jogadores
    decidirem. Uma partida sai dela quando o segundo responde e nunca volta.

    `COMBAT` existe desde já, mas o estado que o combate precisa — o
    pareamento de bloqueadores da §7.2 — entra na feature de combate.

    `FINISHED` também não é fase do ciclo: é o outro lado da partida, o da §10.
    É **terminal** — nenhuma transição sai dela — e está fora de
    `allowed_phases` de toda ação e fora do conjunto de fases automáticas da
    cascata. As duas ausências são o que faz a partida terminada recusar
    qualquer jogada e parar a cascata sem uma linha escrita para isso.
    """

    MULLIGAN = "mulligan"
    UPKEEP = "upkeep"
    ACTION = "action"
    STACK_RESOLUTION = "stack_resolution"
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
    # Fim da lista é o topo: `append` empilha, e a resolução é LIFO (§6).
    stack: list[StackEntry] = field(default_factory=list)
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

        É a revalidação de alvo da §6, e `None` **não é erro**: é a resposta
        que autoriza o fizzle. Quem pergunta não precisa saber de qual jogador
        o alvo é, nem envolver a chamada em `try`.

        Diverge de `player()`, que levanta, porque as perguntas são
        diferentes: pedir um jogador que não joga é bug; perguntar por um alvo
        que sumiu é o caso normal.

        >>> match.bank_unit(CardInstanceId(3)) is None
        True
        """
        for player in self.players:
            found = _unit_in_bank(player.bank, card_instance_id)

            if found is not None:
                return found

        return None

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
