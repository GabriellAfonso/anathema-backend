"""A partida que acabou, depois de o Redis esquecê-la.

Uma linha por partida terminada, e a unicidade de `match_id` é o que garante o
"uma". Entre a gravação do estado e a do banco existe uma janela, e as duas
conexões da mesma partida podem estar em workers diferentes; a restrição é o que
faz a corrida **perder** em vez de duplicar.

`winner` e `loser` são `SET_NULL`, e não `CASCADE`: apagar um perfil não pode
levar junto a linha do histórico do adversário. O que se perde é a identidade de
quem foi apagado -- o desfecho continua legível do lado que sobrou, porque quem
não é `loser` é `winner`.

**Não existe coluna espelho de `user_id`.** `PlayerProfile.user` é a chave
primária (decisão 0001 do vault), então `winner_id` **é** o `user_id`. Uma
segunda coluna com o mesmo inteiro não daria erro quando divergisse: daria
histórico errado que passa despercebido, que é o argumento de `MatchOutcome`.
"""

from django.db import models

from apps.game.match import MatchEndReason
from apps.players.models.player import PlayerProfile

# O `match_id` é o `uuid4()` de `start_match`, em texto. Folga sobre os 36
# caracteres para o dia em que a forma mudar.
MATCH_ID_LENGTH = 64

# Mesmo teto de `PlayerDeck.name`: é uma cópia dele.
DECK_NAME_LENGTH = 50


class MatchRecord(models.Model):
    """O resultado de uma partida, ligado aos dois perfis.

    Escrito uma vez e nunca alterado: não há `updated_at` e nenhuma rota o
    edita. O que aconteceu, aconteceu.

    >>> MatchRecord.objects.get(match_id="m-1").end_reason
    'forfeit'
    """

    # A amarra com o que os clientes viram no socket da partida, e a chave da
    # unicidade que resolve a corrida.
    #
    # Chave **primária**, e não uma coluna única ao lado de um `id` automático:
    # a identidade da linha já é o `match_id`, e um `id` pelado é exatamente o
    # que o princípio II da constituição recusa. Sem ele não há o que expor por
    # engano.
    match_id = models.CharField(max_length=MATCH_ID_LENGTH, primary_key=True)
    winner = models.ForeignKey(
        PlayerProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="matches_won",
    )
    loser = models.ForeignKey(
        PlayerProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="matches_lost",
    )
    # Conjunto fechado da §10: Nexus a zero ou desistência. Não existe empate e
    # não existe derrota por abandono.
    #
    # `.value` nos dois lados de propósito: sem ele a migração serializa o
    # **membro** do enum e passa a importar `MatchEndReason`, e renomear o enum
    # depois quebraria uma migração já aplicada.
    end_reason = models.CharField(
        max_length=20,
        choices=[(reason.value, reason.value) for reason in MatchEndReason],
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    # Guardada, e não recalculada de `ended_at - started_at` na leitura: é este
    # o número que somou em `PlayerStats.play_time`, e os dois têm de bater
    # mesmo numa partida cujo começo se perdeu.
    duration_seconds = models.PositiveIntegerField()
    final_round = models.PositiveIntegerField()
    # `IntegerField` e não `PositiveIntegerField`: o Nexus chega a zero **ou
    # menos** (§10), e o dano de combate não para no zero.
    winner_final_nexus = models.IntegerField()
    loser_final_nexus = models.IntegerField()
    # Cópia congelada do deck da entrada na fila, não referência ao `PlayerDeck`:
    # ele pode ser renomeado ou apagado, e a linha precisa sobreviver a isso.
    # `blank` porque partida gravada antes da feature 012 registra sem nome.
    winner_deck_name = models.CharField(max_length=DECK_NAME_LENGTH, blank=True)
    loser_deck_name = models.CharField(max_length=DECK_NAME_LENGTH, blank=True)
    # `JSONField` e não tabela de junção, pelo mesmo argumento de
    # `PlayerDeck.card_ids`: é uma **lista**, repetição é esperada, a ordem é a
    # que o jogador montou, e ela só é lida inteira.
    winner_deck_card_ids = models.JSONField(default=list)
    loser_deck_card_ids = models.JSONField(default=list)

    class Meta:
        verbose_name = "Match Record"
        verbose_name_plural = "Match Records"
        # Os dois índices que a listagem do histórico usa: ela filtra por um
        # lado ou pelo outro e ordena por `-ended_at`.
        indexes = [
            models.Index(fields=["winner", "-ended_at"]),
            models.Index(fields=["loser", "-ended_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.match_id} ({self.end_reason})"
