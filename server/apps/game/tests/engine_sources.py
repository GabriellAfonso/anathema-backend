"""Os módulos do motor, para os testes que afirmam o que ele **não** faz.

Duas varreduras fazem a mesma pergunta sobre a mesma lista: `test_full_match.py`
prova que o motor não importa transporte nem persistência, e
`test_engine_reads_no_time.py` prova que ele não lê tempo (§15). A lista mora
aqui para não ser escrita duas vezes.

Não é fake: não substitui I/O nenhum, e por isso é uma função e não uma classe.
"""

from pathlib import Path


def engine_sources() -> list[Path]:
    """Todo módulo de `apps/game/engine/`, em ordem.

    >>> engine_sources()[0].parent.name
    'engine'
    """
    root = Path(__file__).resolve().parent.parent

    return sorted((root / "engine").glob("*.py"))
