"""Human-readable status-effect descriptions for the state encoder.

Sibling of `../card_data/card_text.py`, for buffs / debuffs / powers. The engine
exposes status *identity* (`PlayerStatus` / `MonsterStatus`) and a stack count, but no
effect text, so the policy sees "Vulnerable 2" without knowing what Vulnerable does.
This module is the lookup: `status id -> {text, kind, ...}`, loaded from
`status_data.json` (built from the engine headers by `build_status_data.py`).

Scope is both enums in full — 86 player statuses, 42 monster statuses.

    describe_status(sts.PlayerStatus.VULNERABLE, 2)   # 'Vulnerable (2): You take 50%...'
    status_glossary(gi.player_statuses())             # dedup'd block for the whole set
    get_status_text(sts.MonsterStatus.WEAK)           # just the effect text

`status` may be a `PlayerStatus`/`MonsterStatus` enum value or the plain id string
('VULNERABLE'). The same name lives in both enums (Weak, Strength, Thorns, ...) with
text written from opposite sides, so the enum type picks the side; for a bare string,
pass `owner='MONSTER'` when you mean the enemy's copy (default is the player's).
"""
import json
import re
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "status_data.json"

with _DATA_PATH.open(encoding="utf-8") as _f:
    _ALL: dict[str, dict[str, dict]] = json.load(_f)

PLAYER_STATUS_DATA: dict[str, dict] = _ALL["PLAYER"]
MONSTER_STATUS_DATA: dict[str, dict] = _ALL["MONSTER"]

# Enum class name -> section, so a PlayerStatus/MonsterStatus value resolves on its own.
_OWNER_OF_ENUM = {"PlayerStatus": "PLAYER", "MonsterStatus": "MONSTER"}

# The stack-count placeholder in the authored text.
_X = re.compile(r"\bX\b")


def _resolve(status, owner=None) -> tuple[str, str]:
    """Normalize any accepted status form to (status_id_string, owner).

    Accepts a PlayerStatus/MonsterStatus enum value, whose type says which side it
    belongs to, or a plain string. An explicit `owner` arg wins.
    """
    name = getattr(status, "name", status)      # enum -> 'VULNERABLE'; else assume a str
    if owner is None:
        owner = _OWNER_OF_ENUM.get(type(status).__name__)
    if owner is None:
        # A bare string: default to the player's copy, but fall back to the monster
        # table for the ones only monsters have (Curl Up, Mode Shift, ...).
        sid = str(name).upper()
        owner = "PLAYER" if sid in PLAYER_STATUS_DATA else "MONSTER"
    return str(name).upper(), str(owner).upper()


def get(status, owner=None) -> dict | None:
    """Raw data dict for a status, or None if the id isn't in that side's enum."""
    sid, side = _resolve(status, owner)
    return _ALL.get(side, {}).get(sid)


def get_status_text(status, owner=None) -> str:
    """Just the effect text; '' for an unknown status."""
    data = get(status, owner)
    return data["text"] if data else ""


def describe_status(status, amount=None, owner=None) -> str:
    """One line: 'Vulnerable (2): You take 50% more damage from attacks. ...'

    `amount` is the stack count from `get_status`; None describes the status generically,
    and flag-only powers never show a count. Statuses the engine doesn't fully implement
    carry their caveat at the end. Falls back to the raw id for anything unknown.
    """
    sid, side = _resolve(status, owner)
    data = _ALL.get(side, {}).get(sid)
    if data is None:
        return sid  # unknown status: at least name it
    head = data["name"]
    text = data["text"]
    if amount is not None and data["stacks"]:
        head += f" ({amount})"
        # The authored text says "X" where the stack count goes; with a live count in
        # hand, spell it out ("gain X Block" -> "gain 4 Block").
        text = _X.sub(str(amount), text)
    line = f"{head}: {text}"
    if data["engine_note"]:
        line += f" [engine: {data['engine_note']}]"
    return line


def status_glossary(statuses, header: str | None = None) -> str:
    """A de-duplicated description block for a collection of statuses.

    Accepts bare statuses or the `(status, amount)` pairs `env/game_interface.py`
    returns. Each distinct status is described once, in first-seen order; the first
    amount seen for it wins.
    """
    seen: set[tuple[str, str]] = set()
    lines: list[str] = []
    for entry in statuses:
        status, amount = entry if isinstance(entry, tuple) else (entry, None)
        key = _resolve(status)
        if key in seen:
            continue
        seen.add(key)
        lines.append(describe_status(status, amount))
    body = "\n".join(f"- {ln}" for ln in lines)
    return f"{header}\n{body}" if header else body


if __name__ == "__main__":
    print(describe_status("VULNERABLE", 2))
    print(describe_status("VULNERABLE", 2, owner="MONSTER"))
    print(describe_status("BARRICADE", 1))          # flag-only: no count
    print(describe_status("THE_BOMB", 40))          # carries an engine caveat
    print(describe_status("CURL_UP", 5))            # monster-only id, no owner needed

    print("\n" + status_glossary(
        [("WEAK", 2), ("STRENGTH", 3), ("WEAK", 9)], header="Player statuses:"
    ))
    print(f"\nLoaded {len(PLAYER_STATUS_DATA)} player + {len(MONSTER_STATUS_DATA)} monster statuses.")
