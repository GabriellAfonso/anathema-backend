"""O gravador de resultado em memória, para os testes de socket e de relógio.

O `conftest.py` deste pacote registra que nenhum teste de websocket toca o
banco. Com o gravador chegando ao consumer por porta injetada, isto é o que
mantém a regra: quem prova a gravação de verdade é
`apps/game/tests/test_finished_match_record.py`, com `django_db`.

Reproduz a **unicidade por `match_id`** de propósito. Um fake que aceitasse duas
gravações da mesma partida deixaria passar um consumer que registra duas vezes,
e é exatamente esse o bug que a feature existe para não ter.
"""

from apps.game.history import FinishedMatch, FinishedMatchRecorder


class FakeFinishedMatchRecorder:
    """Resultados gravados, em memória, com a mesma regra de unicidade.

    >>> recorder = FakeFinishedMatchRecorder()
    >>> await recorder.record(finished)
    True
    >>> await recorder.record(finished)   # mesma partida, de novo
    False
    >>> len(recorder.recorded)
    1
    """

    def __init__(self) -> None:
        self.recorded: list[FinishedMatch] = []
        # Quando ligado, toda gravação levanta. É como o teste prova que uma
        # falha de banco não impede os dois jogadores de verem o fim.
        self.fails = False

    def record_of(self, match_id: str) -> FinishedMatch | None:
        """O registro daquela partida, ou `None`.

        >>> recorder.record_of("m-1").final_round
        8
        """
        for finished in self.recorded:
            if finished.match_id == match_id:
                return finished

        return None

    async def record(self, finished: FinishedMatch) -> bool:
        if self.fails:
            raise RuntimeError(f"fake recorder refusing to write {finished.match_id!r}")

        if self.record_of(finished.match_id) is not None:
            return False

        self.recorded.append(finished)

        return True


# Asserção estática, não código de teste: conformidade de Protocol em Python só
# é conferida em ponto de atribuição, e esta é a única do arquivo. Sem ela, o
# dia em que `FinishedMatchRecorder` ganhar um método o fake fica para trás em
# silêncio e só quebra na cara de quem for injetá-lo. Não apague por parecer
# sobra.
FAKE_RECORDER_MATCHES_THE_PROTOCOL: FinishedMatchRecorder = FakeFinishedMatchRecorder()
