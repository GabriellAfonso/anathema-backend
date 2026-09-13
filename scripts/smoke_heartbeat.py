"""O heartbeat da partida de fumaça: ping mandado, pong conferido, latência medida.

É o que o `Heartbeat` do cliente Unity faz, reduzido ao que a fumaça precisa
provar (feature 013): todo ping recebe exatamente um pong, o eco volta igual, o
payload que não é objeto volta como `{}`, e a resposta chega depressa.

Módulo separado porque `smoke_match.py` já está perto das 500 linhas que a
constituição permite por arquivo. Não importa nada de lá: devolve os problemas
em texto, e quem chama decide como falhar.
"""

import json
import time
from dataclasses import dataclass, field

# Folga de sobra para um detector que declara queda depois de 30s (SC-010).
LATENCY_LIMIT_MS = 1000.0
INVALID_PING_PAYLOAD = 42


@dataclass
class HeartbeatLedger:
    """O que um bot mandou e recebeu de heartbeat, num socket ou em vários."""

    # Marcador -> `time.monotonic()` do envio, até o pong dele chegar.
    sent_at: dict[int, float] = field(default_factory=dict)
    # Pings com payload inválido ainda sem pong: cada um espera um `{}`.
    invalid_pending: int = 0
    pings: int = 0
    pongs: int = 0
    wrong_echoes: list[str] = field(default_factory=list)
    worst_latency_ms: float = 0.0
    # Fases da partida que já receberam o ping delas.
    phases_seen: set[str] = field(default_factory=set)


def phase_ping_frames(ledger: HeartbeatLedger, phase: str) -> list[str]:
    """Os pings a mandar ao ver um estado: um na primeira vez de cada fase, e o
    de payload inválido uma vez só, na primeira Fase de Ação.

    >>> for frame in phase_ping_frames(ledger, "action"):
    ...     await socket.send(frame)
    """
    if phase in ledger.phases_seen:
        return []

    ledger.phases_seen.add(phase)
    frames = [ping_frame(ledger)]

    if phase == "action":
        frames.append(invalid_ping_frame(ledger))

    return frames


def awaits_pongs(ledger: HeartbeatLedger) -> bool:
    """Se ainda falta pong a chegar -- o socket não pode fechar antes dele.

    >>> awaits_pongs(ledger)
    False
    """
    return ledger.pongs < ledger.pings


def ping_frame(ledger: HeartbeatLedger) -> str:
    """O ping com um marcador novo, já anotado como mandado.

    >>> socket.send(ping_frame(ledger))
    """
    marker = ledger.pings
    ledger.pings += 1
    ledger.sent_at[marker] = time.monotonic()

    return json.dumps({"type": "ping", "payload": {"smoke_marker": marker}})


def invalid_ping_frame(ledger: HeartbeatLedger) -> str:
    """Um ping cujo payload não é objeto: o pong dele tem de vir com `{}`.

    >>> socket.send(invalid_ping_frame(ledger))
    """
    ledger.pings += 1
    ledger.invalid_pending += 1

    return json.dumps({"type": "ping", "payload": INVALID_PING_PAYLOAD})


def record_pong(ledger: HeartbeatLedger, payload: object) -> None:
    """Casa o pong com o ping que o originou e mede a ida e volta.

    >>> record_pong(ledger, {"smoke_marker": 0})
    """
    ledger.pongs += 1

    if payload == {}:
        record_empty_echo(ledger)
        return

    marker = payload.get("smoke_marker") if isinstance(payload, dict) else None
    sent = ledger.sent_at.pop(marker, None) if isinstance(marker, int) else None

    if sent is None or payload != {"smoke_marker": marker}:
        ledger.wrong_echoes.append(repr(payload))
        return

    elapsed_ms = (time.monotonic() - sent) * 1000
    ledger.worst_latency_ms = max(ledger.worst_latency_ms, elapsed_ms)


def record_empty_echo(ledger: HeartbeatLedger) -> None:
    """`{}` só é eco certo para um ping com payload inválido ainda pendente."""
    if ledger.invalid_pending == 0:
        ledger.wrong_echoes.append("{} sem ping inválido pendente")
        return

    ledger.invalid_pending -= 1


def heartbeat_problems(ledger: HeartbeatLedger, label: str) -> list[str]:
    """O que o heartbeat deste bot fez de errado, em texto; vazio se nada.

    >>> heartbeat_problems(ledger, "P1")
    []
    """
    problems = [f"{label}: eco errado {echo}" for echo in ledger.wrong_echoes]

    if ledger.pongs != ledger.pings:
        problems.append(f"{label}: {ledger.pings} pings, {ledger.pongs} pongs")

    if ledger.worst_latency_ms >= LATENCY_LIMIT_MS:
        problems.append(f"{label}: pong em {ledger.worst_latency_ms:.0f}ms")

    return problems


def heartbeat_summary(ledger: HeartbeatLedger) -> str:
    """Uma linha para o relatório da fumaça.

    >>> heartbeat_summary(ledger)
    'pings 7, pongs 7, pior latência 3ms'
    """
    return (
        f"pings {ledger.pings}, pongs {ledger.pongs}, "
        f"pior latência {ledger.worst_latency_ms:.0f}ms"
    )
