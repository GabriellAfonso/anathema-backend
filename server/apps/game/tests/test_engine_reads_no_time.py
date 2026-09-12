"""O motor não lê tempo (§15), verificado no código.

O relógio da vez é problema de transporte: nenhum módulo do motor importa
`time`, nenhum importa o relógio injetado nem o estado de prazo da partida, e
nenhum lê `match.clock`. Sem este teste, a primeira pessoa com pressa resolveria
um cenário de relógio dentro de uma regra, e a §15 -- que diz que o motor não
muda por causa do relógio -- deixaria de ser verdade sem ninguém notar.

A varredura é no código, e não em `sys.modules`: a pergunta é sobre **estes**
arquivos, e o pytest já importou meio mundo.
"""

import ast
from pathlib import Path

from apps.game.tests.engine_sources import engine_sources

FORBIDDEN_MODULES = frozenset(
    {
        "time",
        "datetime",
        "apps.game.wall_clock",
        "apps.game.match.match_clock",
        "wall_clock",
        "match_clock",
    }
)

# Nomes do relógio que poderiam entrar por `from apps.game.match import ...`, que
# o motor já importa por outros motivos.
FORBIDDEN_NAMES = frozenset(
    {
        "MatchClock",
        "TurnDeadline",
        "IDLE_MATCH_CLOCK",
        "clock_wake_at",
        "EpochMillis",
        "WallClock",
        "SystemWallClock",
    }
)

CLOCK_ATTRIBUTE = "clock"


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_modules(tree: ast.Module) -> list[str]:
    """Os módulos importados, relativos inclusive, pelo nome escrito no código."""
    modules: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")

    return modules


def imported_names(tree: ast.Module) -> list[str]:
    return [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]


def test_the_engine_imports_no_clock_module() -> None:
    offenders = [
        (path.name, module)
        for path in engine_sources()
        for module in imported_modules(parsed(path))
        if module in FORBIDDEN_MODULES
    ]

    assert offenders == []


def test_the_engine_imports_no_clock_name() -> None:
    offenders = [
        (path.name, name)
        for path in engine_sources()
        for name in imported_names(parsed(path))
        if name in FORBIDDEN_NAMES
    ]

    assert offenders == []


def test_the_engine_never_reads_the_match_clock() -> None:
    """Nem por atributo: `match.clock` no motor é a §15 vazando para a regra."""
    offenders = [
        (path.name, node.lineno)
        for path in engine_sources()
        for node in ast.walk(parsed(path))
        if isinstance(node, ast.Attribute) and node.attr == CLOCK_ATTRIBUTE
    ]

    assert offenders == []


def test_the_scan_would_catch_an_offender() -> None:
    """A varredura falha quando deve -- senão ela passaria vazia para sempre."""
    tree = ast.parse("import time\nfrom apps.game.match import MatchClock\nx = m.clock")

    assert set(imported_modules(tree)) & FORBIDDEN_MODULES == {"time"}
    assert set(imported_names(tree)) & FORBIDDEN_NAMES == {"MatchClock"}
    assert [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == CLOCK_ATTRIBUTE
    ] == [CLOCK_ATTRIBUTE]
