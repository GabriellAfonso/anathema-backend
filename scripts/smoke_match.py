"""Partida de fumaça: dois bots jogam uma partida inteira contra o servidor local.

Não é teste da suíte: depende do servidor rodando de verdade, com Redis,
uvicorn e lifespan. Passa por tudo que o cliente Unity vai passar -- cadastro,
login, deck inicial, fila, `match_found`, socket de partida, mulligan, rodadas,
fim da partida e histórico pelo HTTP.

Uso, com `docker compose up` rodando:

    venv/Scripts/python scripts/smoke_match.py

Os bots jogam uma estratégia burra e determinística: feitiço que tiver alvo,
atacar com o banco inteiro quando tem o token, jogar a unidade mais barata, e
passar. Na defesa bloqueiam o primeiro atacante. Passando de ROUND_CAP rodadas,
quem tem a vez desiste -- o fim por desistência também precisa funcionar.
"""

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

import websockets

ROUND_CAP = 30
MATCH_TIMEOUT_S = 600
REFUSAL_LIMIT = 20
PASSWORD = "smoke-pass-123"

Json = dict[str, object]
Candidate = tuple[str, Json]


class SmokeFailure(Exception):
    """A partida de fumaça encontrou algo que um cliente real encontraria."""


# --- HTTP --------------------------------------------------------------------


def http(
    base: str, method: str, path: str, body: Json | None = None, token: str = ""
) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as refused:
        raw = refused.read()
        try:
            return refused.code, json.loads(raw)
        except ValueError:
            return refused.code, raw.decode(errors="replace")[:300]


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def sign_up(base: str, username: str) -> str:
    status, body = http(
        base,
        "POST",
        "/accounts/register/",
        {
            "username": username,
            "email": f"{username}@smoke.local",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )
    expect(status == 201, f"cadastro de {username}: {status} {body}")
    return log_in(base, username)


def log_in(base: str, username: str) -> str:
    status, body = http(
        base, "POST", "/accounts/login/", {"username": username, "password": PASSWORD}
    )
    expect(status == 200 and isinstance(body, dict), f"login {username}: {status} {body}")
    assert isinstance(body, dict)
    return str(body["token"])


def first_deck_id(base: str, token: str) -> int:
    status, body = http(base, "GET", "/players/decks/", token=token)
    expect(status == 200 and isinstance(body, dict), f"decks: {status} {body}")
    assert isinstance(body, dict)
    decks = body["decks"]
    expect(isinstance(decks, list) and len(decks) > 0, f"conta nova sem deck: {body}")
    assert isinstance(decks, list)
    return int(decks[0]["deck_id"])


def card_catalog(base: str, token: str) -> dict[int, Json]:
    status, body = http(base, "GET", "/game/cards/", token=token)
    expect(status == 200 and isinstance(body, dict), f"catálogo: {status} {body}")
    assert isinstance(body, dict)
    cards = body["cards"]
    assert isinstance(cards, list)
    return {int(card["card_id"]): card for card in cards}


# --- Bot ---------------------------------------------------------------------


@dataclass
class Bot:
    label: str
    username: str
    token: str
    ws_base: str
    catalog: dict[int, Json]
    names: dict[int, str]
    narrates: bool
    user_id: int = 0
    match_id: str = ""
    view: Json = field(default_factory=dict)
    version: int = -1
    tried: set[tuple[int, str, str]] = field(default_factory=set)
    sent: Counter[str] = field(default_factory=Counter)
    refusals: list[str] = field(default_factory=list)
    mulligan_sent: bool = False
    withdrew_once: bool = False
    outcome: Json | None = None
    # --stall: fica parado na primeira vez da Fase de Ação, para o relógio agir.
    stall_pending: bool = False
    # --forfeit-at: desiste ao chegar nesta rodada com a vez na mão.
    forfeit_round: int = ROUND_CAP + 1


async def find_match(bot: Bot, deck_id: int) -> None:
    url = f"{bot.ws_base}/ws/matchmaking/?token={bot.token}"
    async with websockets.connect(url) as socket:
        join = {"type": "join_queue", "payload": {"deck_id": deck_id}}
        await socket.send(json.dumps(join))
        while True:
            frame = json.loads(await socket.recv())
            if frame["type"] == "match_found":
                payload = frame["payload"]
                bot.user_id = payload["self"]["user_id"]
                bot.match_id = payload["match_id"]
                bot.names[bot.user_id] = bot.label
                return
            raise SmokeFailure(f"{bot.label} na fila recebeu {frame}")


async def play_match(bot: Bot) -> None:
    url = f"{bot.ws_base}/ws/match/?matchId={bot.match_id}&token={bot.token}"
    async with websockets.connect(url) as socket:
        async for raw in socket:
            if not await on_frame(bot, socket, json.loads(raw)):
                return


async def on_frame(bot: Bot, socket: websockets.ClientConnection, frame: Json) -> bool:
    kind = frame["type"]
    payload = frame.get("payload") or {}
    assert isinstance(payload, dict)

    if kind in ("match_start", "match_update"):
        return await on_state(bot, socket, payload)
    if kind == "message_refused":
        return await on_refusal(bot, socket, payload)
    if kind == "turn_warning":
        print(f"   ! {bot.label} recebeu turn_warning {payload}")
        return True
    raise SmokeFailure(f"{bot.label} recebeu frame inesperado: {frame}")


async def on_state(bot: Bot, socket: websockets.ClientConnection, payload: Json) -> bool:
    version = int(payload["version"])  # type: ignore[call-overload]
    if version <= bot.version:
        return True

    bot.version = version
    bot.view = payload["view"]  # type: ignore[assignment]
    narrate(bot, payload.get("events") or [])

    if bot.view["phase"] == "finished":
        bot.outcome = bot.view["outcome"]  # type: ignore[assignment]
        return False

    await act(bot, socket)
    return True


async def on_refusal(bot: Bot, socket: websockets.ClientConnection, payload: Json) -> bool:
    line = f"{payload.get('code')}: {payload.get('error')}"
    bot.refusals.append(line)
    print(f"   x {bot.label} recusado -- {line}")
    expect(len(bot.refusals) <= REFUSAL_LIMIT, f"{bot.label} recusado demais")
    await act(bot, socket)
    return True


# --- Decisão -----------------------------------------------------------------


async def act(bot: Bot, socket: websockets.ClientConnection) -> None:
    view = bot.view
    if view["phase"] == "mulligan":
        await take_mulligan(bot, socket)
        return
    if view["priority_user_id"] != bot.user_id:
        return
    if int(view["round_number"]) >= bot.forfeit_round:  # type: ignore[call-overload]
        await send(bot, socket, ("forfeit", {}))
        return
    if bot.stall_pending and view["phase"] == "action":
        bot.stall_pending = False
        print(f"   ~ {bot.label} fica parado até o relógio estourar (~45s)")
        return

    choose = {
        "action": action_candidates,
        "declaration": declaration_candidates,
        "combat": defense_candidates,
    }[str(view["phase"])]
    for candidate in choose(bot, view):
        if key_of(bot, candidate) not in bot.tried:
            await send(bot, socket, candidate)
            return
    raise SmokeFailure(f"{bot.label} ficou sem jogada em {view['phase']}")


async def take_mulligan(bot: Bot, socket: websockets.ClientConnection) -> None:
    """P1 troca a primeira carta, P2 não troca nada: os dois caminhos."""
    you = bot.view["you"]
    assert isinstance(you, dict)
    if you["mulligan_taken"] or bot.mulligan_sent:
        return
    swapped = [you["hand"][0]["card_instance_id"]] if bot.label == "P1" else []
    bot.mulligan_sent = True
    await send(bot, socket, ("mulligan", {"card_instance_ids": swapped}))


def action_candidates(bot: Bot, view: Json) -> Iterator[Candidate]:
    you, opponent = view["you"], view["opponent"]
    assert isinstance(you, dict) and isinstance(opponent, dict)
    yield from spell_candidates(bot, you, opponent, declaration=False)

    bank = [unit["card"]["card_instance_id"] for unit in you["bank"]]
    if view["token_holder_user_id"] == bot.user_id and not view["token_consumed"] and bank:
        yield "declare_attack", {"attacker_card_instance_ids": bank}

    for card in sorted(you["hand"], key=lambda c: bot.catalog[c["card_id"]]["energy"]):
        spec = bot.catalog[card["card_id"]]
        affordable = spec["energy"] <= you["energy_current"]
        if spec["card_type"] == "unit" and affordable and len(bank) < 6:
            yield "play_unit", {"card_instance_id": card["card_instance_id"]}
    yield "pass", {}


def declaration_candidates(bot: Bot, view: Json) -> Iterator[Candidate]:
    you, opponent, combat = view["you"], view["opponent"], view["combat"]
    assert isinstance(you, dict) and isinstance(combat, dict)
    zone = combat["attacker_card_instance_ids"]
    if not bot.withdrew_once and len(zone) >= 2:
        yield "withdraw_attacker", {"attacker_card_instance_id": zone[-1]}
    yield from spell_candidates(bot, you, opponent, declaration=True)
    yield "confirm_attack", {}


def defense_candidates(bot: Bot, view: Json) -> Iterator[Candidate]:
    you, combat = view["you"], view["combat"]
    assert isinstance(you, dict) and isinstance(combat, dict)
    attackers = combat["attacker_card_instance_ids"]
    if not combat["blocks"] and attackers and you["bank"]:
        blocker = you["bank"][0]["card"]["card_instance_id"]
        yield "assign_blocker", {
            "blocker_card_instance_id": blocker,
            "attacker_card_instance_id": attackers[0],
        }
    yield "end_defense_window", {}


def spell_candidates(
    bot: Bot, you: Json, opponent: Json, *, declaration: bool
) -> Iterator[Candidate]:
    for card in you["hand"]:  # type: ignore[attr-defined]
        spec = bot.catalog[card["card_id"]]
        if spec["card_type"] != "spell" or spec["energy"] > you["energy_current"]:
            continue
        effect = spec["effect"]
        if effect["declaration_only"] != declaration:  # type: ignore[index]
            continue
        if spec["name"] == "LIFE POTION" and you["nexus"] >= 12:  # type: ignore[operator]
            continue
        target = pick_target(str(effect["target_kind"]), you, opponent)  # type: ignore[index]
        if target is not False:
            yield "cast_spell", {
                "card_instance_id": card["card_instance_id"],
                "target_card_instance_id": target,
            }


def pick_target(target_kind: str, you: Json, opponent: Json) -> int | None | bool:
    """O alvo, `None` para feitiço sem alvo, ou `False` quando não há alvo."""
    if target_kind == "none":
        return None
    pool = {"allied_unit": you["bank"], "enemy_unit": opponent["bank"]}.get(target_kind)
    if not pool:
        return False
    return int(pool[0]["card"]["card_instance_id"])  # type: ignore[index]


def key_of(bot: Bot, candidate: Candidate) -> tuple[int, str, str]:
    return bot.version, candidate[0], json.dumps(candidate[1], sort_keys=True)


async def send(bot: Bot, socket: websockets.ClientConnection, candidate: Candidate) -> None:
    kind, payload = candidate
    bot.tried.add(key_of(bot, candidate))
    bot.sent[kind] += 1
    if kind == "withdraw_attacker":
        bot.withdrew_once = True
    await socket.send(json.dumps({"type": kind, "payload": payload}))


# --- Narração ----------------------------------------------------------------


def narrate(bot: Bot, events: object) -> None:
    """Uma linha por evento, só pelos olhos de P1 -- os dois recebem os mesmos."""
    if not bot.narrates or not isinstance(events, list):
        return
    for event in events:
        print(f"R{bot.view['round_number']:>2} {describe(bot, event)}")


def describe(bot: Bot, event: Json) -> str:
    parts = [str(event["kind"])]
    for name, value in event.items():
        if name == "kind":
            continue
        parts.append(f"{name}={shown(bot, name, value)}")
    return " ".join(parts)


def shown(bot: Bot, name: str, value: object) -> object:
    if name.endswith("user_id") and value in bot.names:
        return bot.names[value]  # type: ignore[index]
    if isinstance(value, dict) and "card_id" in value:
        return bot.catalog[value["card_id"]]["name"]
    if isinstance(value, list):
        return f"[{len(value)}]"
    return value


# --- Roteiro -----------------------------------------------------------------


def check_history(base: str, bots: list[Bot]) -> None:
    for bot in bots:
        token = log_in(base, bot.username)
        status, body = http(base, "GET", "/game/matches/?page_size=5", token=token)
        expect(status == 200 and isinstance(body, dict), f"histórico: {status} {body}")
        assert isinstance(body, dict)
        rows = [row for row in body["results"] if row["match_id"] == bot.match_id]
        expect(len(rows) == 1, f"{bot.label}: partida no histórico {len(rows)} vezes")
        row = rows[0]
        print(
            f"   {bot.label} histórico: won={row['won']} reason={row['end_reason']} "
            f"final_round={row['final_round']} duration={row['duration_seconds']}s"
        )
    expect(
        {row_won(base, bot) for bot in bots} == {True, False},
        "o histórico não tem exatamente um vencedor e um perdedor",
    )


def row_won(base: str, bot: Bot) -> bool:
    token = log_in(base, bot.username)
    _, body = http(base, "GET", "/game/matches/?page_size=5", token=token)
    assert isinstance(body, dict)
    return next(r["won"] for r in body["results"] if r["match_id"] == bot.match_id)


def spell_deck_id(base: str, token: str) -> int:
    """25 unidades baratas e os 5 feitiços com 3 cópias: o deck inicial não tem
    feitiço nenhum, e sem isto a partida nunca lança um."""
    cards = [c for c in range(1, 9) for _ in range(3)] + [9]
    cards += [s for s in range(1001, 1006) for _ in range(3)]
    status, body = http(
        base, "POST", "/players/decks/", {"name": "Fumaça", "card_ids": cards}, token
    )
    expect(status == 201 and isinstance(body, dict), f"criar deck: {status} {body}")
    assert isinstance(body, dict)
    return int(body["deck_id"])  # type: ignore[call-overload]


async def run(base: str, options: argparse.Namespace) -> None:
    ws_base = base.replace("http", "ws", 1)
    suffix = str(int(time.time()))
    names: dict[int, str] = {}

    bots = []
    for label in ("P1", "P2"):
        username = f"smoke_{label.lower()}_{suffix}"
        token = sign_up(base, username)
        catalog = card_catalog(base, token)
        bot = Bot(label, username, token, ws_base, catalog, names, label == "P1")
        bot.stall_pending = options.stall and label == "P2"
        bot.forfeit_round = options.forfeit_at or ROUND_CAP + 1
        bots.append(bot)
    pick = spell_deck_id if options.spells else first_deck_id
    decks = [pick(base, bot.token) for bot in bots]
    print(f"== contas criadas, catálogo com {len(bots[0].catalog)} cartas, decks {decks}")

    await asyncio.gather(*(find_match(bot, deck) for bot, deck in zip(bots, decks)))
    expect(bots[0].match_id == bots[1].match_id, "os dois caíram em partidas diferentes")
    print(f"== pareados na partida {bots[0].match_id}")

    started = time.monotonic()
    await asyncio.wait_for(
        asyncio.gather(*(play_match(bot) for bot in bots)), MATCH_TIMEOUT_S
    )
    report(bots, time.monotonic() - started)
    check_history(base, bots)
    print("== OK")


def report(bots: list[Bot], seconds: float) -> None:
    outcome = bots[0].outcome
    expect(outcome is not None and outcome == bots[1].outcome, "desfechos divergentes")
    assert isinstance(outcome, dict)
    loser = bots[0].names.get(outcome["defeated_user_id"])  # type: ignore[call-overload]
    print(f"== fim em {seconds:.1f}s: perdeu {loser}, motivo {outcome['reason']}")
    for bot in bots:
        print(f"   {bot.label} mandou {dict(bot.sent)}, recusas {len(bot.refusals)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--spells", action="store_true", help="deck com feitiços")
    parser.add_argument("--stall", action="store_true", help="P2 deixa o relógio estourar")
    parser.add_argument("--forfeit-at", type=int, default=0, help="desiste nesta rodada")
    options = parser.parse_args()
    try:
        asyncio.run(run(options.base, options))
    except SmokeFailure as failure:
        print(f"== FALHOU: {failure}")
        sys.exit(1)


if __name__ == "__main__":
    main()
