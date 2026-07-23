"""Human-readable card descriptions for the state encoder.

The sts_lightspeed engine exposes card *identity* (`CardId`) but no effect text,
so the LLM policy has nothing to reason about unless we supply it. This module is
the lookup: `CardId name -> {text, upgraded text, cost, type, ...}`, loaded from
`card_data.json` (generated from the reference spreadsheet by `build_card_data.py`).

Scope is the Ironclad-complete engine's actual card pool — Ironclad, Colorless,
Curses, Statuses (145 cards). No other classes.

Intended consumer: `env/state_encoder.py`. Per the project wiki, the encoder should
render each *distinct* card in play once (a glossary), rather than repeating full
text per duplicate every turn — that's the context-budget tension. `card_glossary()`
does exactly that.

    from card_text import describe_card, card_glossary, get_card_text

    describe_card(card)                 # 'Bash (2 energy, Attack): Deal 8 damage...'
    card_glossary(bc.cards.hand)        # dedup'd block for the whole hand
    get_card_text(card)                 # just the effect text

`card` may be an sts `Card`/`CardInstance` (read via `.id` + `.upgraded`), a
`CardId` enum, or the plain id string ('BASH').
"""
import json
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "card_data.json"

with _DATA_PATH.open(encoding="utf-8") as _f:
    CARD_DATA: dict[str, dict] = json.load(_f)


def _resolve(card, upgraded=None) -> tuple[str, bool]:
    """Normalize any accepted card form to (card_id_string, upgraded_bool).

    Accepts an sts Card/CardInstance (has `.id` and usually `.upgraded`), a CardId
    enum (has `.name`), or a plain string. An explicit `upgraded` arg wins over the
    object's own flag.
    """
    cid = getattr(card, "id", card)          # Card/CardInstance -> CardId; else passthrough
    name = getattr(cid, "name", cid)         # CardId enum -> 'BASH'; else assume already a str
    if upgraded is None:
        upgraded = bool(getattr(card, "upgraded", False))
    return str(name).upper(), bool(upgraded)


def get(card, upgraded=None) -> dict | None:
    """Raw data dict for a card, or None if it's outside our scope."""
    cid, _ = _resolve(card, upgraded)
    return CARD_DATA.get(cid)


def _fmt_cost(data: dict, upgraded: bool) -> str:
    cost = data["cost_upgraded"] if (upgraded and data["cost_upgraded"]) else data["cost"]
    if cost == "Unplayable":
        return "Unplayable"
    if cost == "X":
        return "X energy"
    return f"{cost} energy"


def _display_name(data: dict, upgraded: bool) -> str:
    return data["name"] + ("+" if upgraded else "")


def get_card_text(card, upgraded=None) -> str:
    """Just the effect text (upgraded variant when the card is upgraded and it differs).

    Returns '' for a card outside our scope so callers never crash on a missing id.
    """
    cid, up = _resolve(card, upgraded)
    data = CARD_DATA.get(cid)
    if data is None:
        return ""
    if up and data["text_upgraded"]:
        return data["text_upgraded"]
    return data["text"]


def describe_card(card, upgraded=None) -> str:
    """One line: 'Bash (2 energy, Attack): Deal 8 damage. Apply 2 Vulnerable.'

    Falls back to the raw id for anything outside our scope, so it's always safe to call.
    """
    cid, up = _resolve(card, upgraded)
    data = CARD_DATA.get(cid)
    if data is None:
        return cid  # unknown / out-of-scope card: at least name it
    name = _display_name(data, up)
    cost = _fmt_cost(data, up)
    ctype = data["type"].capitalize()
    return f"{name} ({cost}, {ctype}): {get_card_text(card, up)}"


def card_glossary(cards, header: str | None = None) -> str:
    """A de-duplicated description block for a collection of cards.

    Each distinct (card, upgraded) pair is described once, in first-seen order — so a
    hand of [Strike, Strike, Bash] yields two lines, not three. This is the encoder's
    hand/deck legend; keeping it dedup'd is the whole point (context budget).
    """
    seen: set[tuple[str, bool]] = set()
    lines: list[str] = []
    for c in cards:
        key = _resolve(c)
        if key in seen:
            continue
        seen.add(key)
        lines.append(describe_card(c))
    body = "\n".join(f"- {ln}" for ln in lines)
    return f"{header}\n{body}" if header else body


if __name__ == "__main__":
    # Standalone smoke test (no sts module needed): drive it with id strings and a
    # tiny stand-in object that mimics an sts Card.
    print(describe_card("BASH"))
    print(describe_card("BASH", upgraded=True))
    print(describe_card("BODY_SLAM", upgraded=True))   # cost drops 1 -> 0, text unchanged
    print(describe_card("WOUND"))
    print(describe_card("WHIRLWIND"))

    class _FakeId:
        def __init__(self, name): self.name = name
    class _FakeCard:
        def __init__(self, name, upgraded=False):
            self.id = _FakeId(name); self.upgraded = upgraded

    hand = [_FakeCard("STRIKE_RED"), _FakeCard("STRIKE_RED"),
            _FakeCard("BASH", upgraded=True), _FakeCard("DEFEND_RED")]
    print("\n" + card_glossary(hand, header="Cards in hand:"))
    print(f"\nLoaded {len(CARD_DATA)} cards.")
