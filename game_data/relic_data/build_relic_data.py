"""Generate `relic_data.json` from `Slay the Spire Reference.xlsx`.

Mirror of `../card_data/build_card_data.py`, for relics. The sts_lightspeed engine
exposes relic *identity* (`RelicId`) but no effect text, which the LLM policy needs
to reason about the run. This turns the reference spreadsheet's `Relics` sheet into
a static `RelicId -> {rarity, text, ...}` table keyed by the engine's RelicId enum
names, so `relic_text.py` / the state encoder can look up by `relic.id.name`.

Scope: relics an Ironclad run can actually obtain — shared relics plus Ironclad
class-specific ones. Relics locked to Silent/Defect/Watcher are excluded (matching
the card pipeline's "no other classes" rule).

Re-run after editing the sheet:  python game_data/relic_data/build_relic_data.py
"""
import json
import re
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
XLSX = HERE.parent / "Slay the Spire Reference.xlsx"          # game_data/…
OUT = HERE / "relic_data.json"
BINDINGS = REPO / "sts_lightspeed" / "bindings" / "slaythespire.cpp"

# Relics class-locked to these classes can't appear in an Ironclad run.
EXCLUDED_CLASSES = {"Defect", "Watcher", "Silent"}

# Columns in the Relics sheet (0-based).
COL_NAME, COL_RARITY, COL_CLASS, COL_DESC = 0, 1, 2, 3


def normalize_id(name: str) -> str:
    """Display name -> RelicId enum name ('Du-Vu Doll' -> DU_VU_DOLL)."""
    n = name.strip().upper().replace(".", "").replace("'", "").replace("-", " ")
    return re.sub(r"[^A-Z0-9]+", "_", n).strip("_")


def replace_energy_tokens(text: str) -> str:
    """Collapse runs of energy orbs ('[E] [E]', '[R]') into readable text ('2 Energy')."""
    def repl(m):
        count = len(re.findall(r"\[[A-Z]\]", m.group(0)))
        return f"{count} Energy"
    return re.sub(r"\[[A-Z]\](?:\s*\[[A-Z]\])*", repl, text)


def clean(text) -> str:
    t = replace_energy_tokens(re.sub(r"\s+", " ", str(text).strip()))
    return re.sub(r"\s+([.,;:!?])", r"\1", t)   # drop stray space before punctuation


def load_enum_ids() -> set[str]:
    cpp = BINDINGS.read_text(encoding="utf-8")
    return set(re.findall(r'\.value\("([A-Z0-9_]+)",\s*RelicId::', cpp))


def main() -> None:
    enum_ids = load_enum_ids()
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    rows = list(wb["Relics"].iter_rows(values_only=True))

    relics: dict[str, dict] = {}
    problems: list[str] = []
    bracket_tokens: set[str] = set()
    skipped = 0

    for row in rows[1:]:  # row 0 is the header
        name = row[COL_NAME]
        if not name or not str(name).strip():
            continue
        name = str(name).strip()
        klass = str(row[COL_CLASS]).strip() if row[COL_CLASS] else ""

        if klass in EXCLUDED_CLASSES:
            skipped += 1
            continue

        rid = normalize_id(name)
        if rid not in enum_ids:
            problems.append(f"{name!r} -> {rid!r} not in RelicId enum")

        desc = row[COL_DESC]
        bracket_tokens.update(re.findall(r"\[[^\]]+\]", str(desc)))

        relics[rid] = {
            "name": name,
            "rarity": str(row[COL_RARITY]).strip().upper() if row[COL_RARITY] else "",
            "character": klass or None,   # None = shared; else 'Ironclad'
            "text": clean(desc),
        }

    if problems:
        raise SystemExit("Unmapped relics:\n  " + "\n  ".join(problems))

    OUT.write_text(json.dumps(relics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(relics)} relics -> {OUT.relative_to(REPO)}  (excluded {skipped} other-class)")
    print(f"Bracket tokens seen (should all be energy orbs): {sorted(bracket_tokens)}")
    by_rarity: dict[str, int] = {}
    for r in relics.values():
        by_rarity[r["rarity"]] = by_rarity.get(r["rarity"], 0) + 1
    print("By rarity:", dict(sorted(by_rarity.items())))


if __name__ == "__main__":
    main()
