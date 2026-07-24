"""Human-readable relic descriptions for the state encoder.

Sibling of `../card_data/card_text.py`, for relics. The sts_lightspeed engine
exposes relic *identity* (`RelicId`) but no effect text; this module is the lookup:
`RelicId name -> {text, rarity, ...}`, loaded from `relic_data.json` (generated from
the reference spreadsheet by `build_relic_data.py`).

Scope is what an Ironclad run can obtain — shared + Ironclad relics (149). No relics
locked to other classes.

    from relic_text import describe_relic, relic_glossary, get_relic_text

    describe_relic(relic)            # 'Akabeko (Common): Your first Attack each combat...'
    relic_glossary(gc.relics)        # dedup'd block for the whole relic list
    get_relic_text(relic)            # just the effect text

`relic` may be an sts `Relic` (read via `.id`), a `RelicId` enum, or the id string
('AKABEKO'). Relics have no upgrade dimension, so there's no upgraded variant.
"""
import json
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "relic_data.json"

with _DATA_PATH.open(encoding="utf-8") as _f:
    RELIC_DATA: dict[str, dict] = json.load(_f)


def _resolve(relic) -> str:
    """Normalize any accepted relic form to its id string.

    Accepts an sts Relic (has `.id`), a RelicId enum (has `.name`), or a plain string.
    """
    rid = getattr(relic, "id", relic)        # Relic -> RelicId; else passthrough
    name = getattr(rid, "name", rid)         # RelicId enum -> 'AKABEKO'; else assume str
    return str(name).upper()


def get(relic) -> dict | None:
    """Raw data dict for a relic, or None if it's outside our scope."""
    return RELIC_DATA.get(_resolve(relic))


def get_relic_text(relic) -> str:
    """Just the effect text. Returns '' for a relic outside our scope."""
    data = RELIC_DATA.get(_resolve(relic))
    return data["text"] if data else ""


def describe_relic(relic) -> str:
    """One line: 'Akabeko (Common): Your first Attack each combat deals 8 additional damage.'

    Falls back to the raw id for anything outside our scope, so it's always safe to call.
    """
    rid = _resolve(relic)
    data = RELIC_DATA.get(rid)
    if data is None:
        return rid  # unknown / out-of-scope relic: at least name it
    rarity = data["rarity"].capitalize()
    return f"{data['name']} ({rarity}): {data['text']}"


def relic_glossary(relics, header: str | None = None) -> str:
    """A de-duplicated description block for a collection of relics.

    Each distinct relic is described once, in first-seen order. (Relics are normally
    unique, but dedup keeps the encoder output stable regardless.)
    """
    seen: set[str] = set()
    lines: list[str] = []
    for r in relics:
        rid = _resolve(r)
        if rid in seen:
            continue
        seen.add(rid)
        lines.append(describe_relic(r))
    body = "\n".join(f"- {ln}" for ln in lines)
    return f"{header}\n{body}" if header else body


if __name__ == "__main__":
    print(describe_relic("BURNING_BLOOD"))
    print(describe_relic("MARK_OF_PAIN"))
    print(describe_relic("SOZU"))

    class _FakeId:
        def __init__(self, name): self.name = name
    class _FakeRelic:
        def __init__(self, name): self.id = _FakeId(name)

    relics = [_FakeRelic("BURNING_BLOOD"), _FakeRelic("AKABEKO"), _FakeRelic("ANCHOR")]
    print("\n" + relic_glossary(relics, header="Relics:"))
    print(f"\nLoaded {len(RELIC_DATA)} relics.")
