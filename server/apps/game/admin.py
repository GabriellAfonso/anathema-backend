"""O registro de partida no admin, somente leitura.

Nenhuma rota desta feature altera um registro -- ele é escrito uma vez e o que
aconteceu, aconteceu --, e o admin não devia ser a exceção por onde alguém
conserta um histórico à mão.
"""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from apps.game.models import MatchRecord


@admin.register(MatchRecord)
# `ModelAdmin` só é genérico para o django-stubs; subscrevê-lo em tempo de
# execução levanta `TypeError`. É o que `mypy.ini` já registra em
# `[mypy-apps.*.admin]`, e o que `apps/players/admin.py` já faz.
class MatchRecordAdmin(admin.ModelAdmin):
    list_display = ("match_id", "winner", "loser", "end_reason", "ended_at")
    list_filter = ("end_reason",)
    search_fields = ("match_id",)
    ordering = ("-ended_at",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Any = None
    ) -> bool:
        return False
