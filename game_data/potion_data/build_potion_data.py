"""Generate `potion_data.json` for the state encoder.

Sibling of `../card_data/build_card_data.py`, but the reference spreadsheet has **no
potion sheet**, so the source of truth is the engine itself:

  * `sts_lightspeed/include/constants/Potions.h` supplies the name, rarity, per-class
    pool, and which potions require a target.
  * The effect *text* is hand-authored below (`POTION_TEXT`), transcribed to match the
    base (no Sacred Bark) effect the engine applies in `combat/BattleContext.cpp`.

Scope: `potionPool[0]` — the 33 potions an **Ironclad** run can roll (30 shared + the
3 Ironclad-locked: Blood Potion, Elixir, Heart of Iron).

Engine caveats:
  * Blood Potion: real game heals 20% Max HP, the engine 40% (looks like an inverted
    Sacred Bark check). The text uses the engine's 40%, which is what the agent sees.
  * Smoke Bomb: engine leaves it a `// todo` no-op; real game escapes a non-boss fight.
  * Fairy Potion: passive (auto-revive); it is never actively "drunk".
  * Sacred Bark relic doubles every potion's potency (not reflected per-line here).

Re-run:  python game_data/potion_data/build_potion_data.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
POTIONS_H = REPO / "sts_lightspeed" / "include" / "constants" / "Potions.h"
OUT = HERE / "potion_data.json"

# Hand-authored effect text, keyed by Potion enum name. Must cover exactly the
# Ironclad pool (validated below). Base (no Sacred Bark) values.
POTION_TEXT = {
    # --- Ironclad-locked ---
    "BLOOD_POTION": "Heal 40% of your Max HP.",           # engine base is 40% (game is 20%); text matches engine
    "ELIXIR_POTION": "Exhaust any number of cards in your hand.",
    "HEART_OF_IRON": "Gain 6 Metallicize.",
    # --- shared ---
    "ATTACK_POTION": "Add 1 of 3 random Attack cards to your hand. It costs 0 this turn.",
    "SKILL_POTION": "Add 1 of 3 random Skill cards to your hand. It costs 0 this turn.",
    "POWER_POTION": "Add 1 of 3 random Power cards to your hand. It costs 0 this turn.",
    "COLORLESS_POTION": "Add 1 of 3 random Colorless cards to your hand. It costs 0 this turn.",
    "BLOCK_POTION": "Gain 12 Block.",
    "DEXTERITY_POTION": "Gain 2 Dexterity.",
    "ENERGY_POTION": "Gain 2 Energy.",
    "STRENGTH_POTION": "Gain 2 Strength.",
    "EXPLOSIVE_POTION": "Deal 10 damage to ALL enemies.",
    "FIRE_POTION": "Deal 20 damage to target enemy.",
    "WEAK_POTION": "Apply 3 Weak to target enemy.",
    "FEAR_POTION": "Apply 3 Vulnerable to target enemy.",
    "SWIFT_POTION": "Draw 3 cards.",
    "FLEX_POTION": "Gain 5 Strength. At the end of your turn, lose 5 Strength.",
    "SPEED_POTION": "Gain 5 Dexterity. At the end of your turn, lose 5 Dexterity.",
    "BLESSING_OF_THE_FORGE": "Upgrade all cards in your hand for the rest of combat.",
    "REGEN_POTION": "Gain 5 Regeneration.",
    "ANCIENT_POTION": "Gain 1 Artifact.",
    "LIQUID_BRONZE": "Gain 3 Thorns.",
    "ESSENCE_OF_STEEL": "Gain 4 Plated Armor.",
    "GAMBLERS_BREW": "Discard any number of cards, then draw that many.",
    "DUPLICATION_POTION": "This turn, your next card is played twice.",
    "DISTILLED_CHAOS": "Play the top 3 cards of your draw pile.",
    "LIQUID_MEMORIES": "Choose 1 card in your discard pile and return it to your hand. It costs 0 this turn.",
    "CULTIST_POTION": "Gain 1 Ritual.",
    "FRUIT_JUICE": "Gain 5 Max HP.",
    "SNECKO_OIL": "Draw 5 cards. Randomize the costs of all cards in your hand for the rest of combat.",
    "FAIRY_POTION": "When you would die, heal to 30% of your Max HP instead and discard this potion.",
    "SMOKE_BOMB": "Escape from a non-boss enemy encounter. You receive no rewards.",
    "ENTROPIC_BREW": "Fill all of your empty potion slots with random potions.",
}

_RARITY = {"COMMON": "COMMON", "UNCOMMON": "UNCOMMON", "RARE": "RARE"}
_CONNECTORS = {"of", "the", "in", "a", "and", "to"}


def _quoted_list(block: str) -> list[str]:
    return re.findall(r'"([^"]*)"', block)


def _prettify(name: str) -> str:
    """'Blessing Of The Forge' -> 'Blessing of the Forge' for readability."""
    words = name.split()
    return " ".join(
        w if i == 0 or w.lower() not in _CONNECTORS else w.lower()
        for i, w in enumerate(words)
    )


def parse_potions_h(text: str):
    enum_names = _quoted_list(re.search(r"potionEnumNames\[\]\s*=\s*\{(.*?)\}", text, re.S).group(1))
    display_names = _quoted_list(re.search(r"potionNames\[\]\s*\{(.*?)\}", text, re.S).group(1))
    rarities = re.findall(r"PotionRarity::(\w+)", re.search(r"potionRarities\[\]\s*=\s*\{(.*?)\}", text, re.S).group(1))
    # first inner {...} of potionPool = Ironclad (class index 0)
    pool_block = re.search(r"potionPool\[4\]\[33\]\s*\{\s*\{(.*?)\}", text, re.S).group(1)
    ironclad_pool = re.findall(r"Potion::(\w+)", pool_block)
    target_block = re.search(r"potionRequiresTarget.*?\{(.*?)return true", text, re.S).group(1)
    targets = set(re.findall(r"Potion::(\w+)", target_block))
    return enum_names, display_names, rarities, ironclad_pool, targets


def main() -> None:
    text = POTIONS_H.read_text(encoding="utf-8")
    enum_names, display_names, rarities, ironclad_pool, targets = parse_potions_h(text)

    if not (len(enum_names) == len(display_names) == len(rarities)):
        raise SystemExit(f"Potions.h arrays out of sync: {len(enum_names)}/{len(display_names)}/{len(rarities)}")

    name_of = dict(zip(enum_names, display_names))
    rarity_of = dict(zip(enum_names, rarities))

    pool = set(ironclad_pool)
    missing_text = sorted(pool - set(POTION_TEXT))
    extra_text = sorted(set(POTION_TEXT) - pool)
    if missing_text:
        raise SystemExit("Ironclad-pool potions with no authored text:\n  " + "\n  ".join(missing_text))
    if extra_text:
        raise SystemExit("Authored text for potions not in the Ironclad pool:\n  " + "\n  ".join(extra_text))

    potions: dict[str, dict] = {}
    for pid in ironclad_pool:
        potions[pid] = {
            "name": _prettify(name_of[pid]),
            "rarity": _RARITY.get(rarity_of[pid], rarity_of[pid]),
            "requires_target": pid in targets,
            "text": POTION_TEXT[pid],
        }

    OUT.write_text(json.dumps(potions, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(potions)} potions -> {OUT.relative_to(REPO)}")
    by_rarity: dict[str, int] = {}
    for p in potions.values():
        by_rarity[p["rarity"]] = by_rarity.get(p["rarity"], 0) + 1
    print("By rarity:", dict(sorted(by_rarity.items())))
    print("Require target:", sorted(pid for pid, p in potions.items() if p["requires_target"]))


if __name__ == "__main__":
    main()
