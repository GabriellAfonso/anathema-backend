"""O deck do jogador: a lista de cartas com que ele escolhe jogar.

Um deck pertence a um jogador e só a ele. A identidade é o `deck_id` -- a
chave primária --, nunca o nome: dois decks do mesmo jogador podem se chamar
igual, porque o nome é rótulo de quem montou.

O que valida um deck não está aqui: são as três regras da feature 001
(`apps.game.cards.deck_rules`), aplicadas por
`apps.players.services.deck_validation` no salvamento e pelo socket de
matchmaking na entrada da fila.
"""

from django.db import models

from .player import PlayerProfile


class PlayerDeck(models.Model):
    """Uma lista de `card_id` que pertence a um jogador.

    `card_ids` é `JSONField` e não tabela de junção porque o deck é uma
    **lista**: repetição é esperada, até 3 entradas do mesmo identificador, e a
    ordem é guardada como o jogador enviou. Uma tabela de junção obrigaria ou a
    uma coluna de quantidade -- que destrói a ordem e transforma a lista em
    multiconjunto -- ou a 40 linhas por deck, 800 por jogador no teto, para um
    valor que só é lido inteiro e só é escrito inteiro.

    Não há chave estrangeira para carta porque carta não é linha de banco: o
    catálogo é código congelado, e a integridade de `card_ids` é exatamente o
    que a regra `UnknownDeckCard` da feature 001 confere.

    Sem `unique_together` em `(profile, name)`: nome repetido é aceito.

    >>> PlayerDeck.objects.create(profile=profile, name="Agro", card_ids=[1, 1, 2])
    <PlayerDeck: Agro (deck_id=1)>
    """

    # `profile_id` **é** o `user_id`: `PlayerProfile.user` é a chave primária
    # (decisão 0001 do vault, um perfil por usuário e para sempre).
    profile = models.ForeignKey(
        PlayerProfile, on_delete=models.CASCADE, related_name="decks"
    )
    name = models.CharField(max_length=50)
    card_ids = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Player Deck"
        verbose_name_plural = "Player Decks"

    def __str__(self) -> str:
        return f"{self.name} (deck_id={self.pk})"
