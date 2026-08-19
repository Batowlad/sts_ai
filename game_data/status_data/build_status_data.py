"""Generate `status_data.json` for the state encoder.

Sibling of `../card_data/build_card_data.py` and `../potion_data/build_potion_data.py`,
for status effects (the game's buffs / debuffs / powers). Like potions — and unlike
cards and relics — the reference spreadsheet has **no status sheet**, so the source of
truth is the engine itself:

  * `sts_lightspeed/include/constants/PlayerStatusEffects.h` and
    `.../MonsterStatusEffects.h` supply the authoritative enum order and the display
    names (`playerStatusStrings` / `enemyStatusStrings`, index-aligned to the enums).
  * The effect *text* is hand-authored below — the engine stores none. Wording follows
    the real game; where this engine's implementation differs or is missing, the entry
    carries an `engine_note` so the policy isn't told about behaviour it will never see.

Scope: **every** value of both enums except INVALID (85 player + 42 monster). The other
pipelines cut to the Ironclad pool, but a status has no owning class — monsters apply
what they like, and the table is only rendered for statuses that are actually active, so
full coverage costs nothing at runtime and leaves no gaps.

Two fields beyond name/text:
  * `kind`   — buff / debuff / power, for grouping in the encoder.
  * `stacks` — whether the stack count is meaningful. False for flag-only powers, which
    also matters mechanically: the engine keeps those out of `statusMap`, so
    `Player.get_status` on one raises instead of returning 1 (see `view_statuses`).

Re-run:  python game_data/status_data/build_status_data.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CONSTANTS = REPO / "sts_lightspeed" / "include" / "constants"
PLAYER_H = CONSTANTS / "PlayerStatusEffects.h"
MONSTER_H = CONSTANTS / "MonsterStatusEffects.h"
OUT = HERE / "status_data.json"

# Flag-only player statuses: the stack count carries no meaning. The first seven are
# also the ones `Player::buff`/`debuff` set as a bare bit with no `statusMap` entry, so
# `get_status` on them throws (std::out_of_range -> IndexError) rather than returning 1.
PLAYER_FLAGS = {
    "BARRICADE", "CONFUSED", "CORRUPTION", "DRAW_REDUCTION", "HEX", "PEN_NIB", "SURROUNDED",
    "BLASPHEMER", "ELECTRO", "ENTANGLED", "MASTER_REALITY", "NO_BLOCK", "NO_DRAW",
    "WRATH_NEXT_TURN",
}

# Hand-authored, keyed by PlayerStatus enum name. "X" is the stack count.
# (kind, text) or (kind, text, engine_note).
PLAYER_STATUS = {
    # --- statuses that use justApplied (they skip their first decrement) ---
    "DOUBLE_DAMAGE": ("buff", "Your Attacks deal double damage this turn."),
    "DRAW_REDUCTION": ("debuff", "You draw 1 fewer card next turn."),
    "FRAIL": ("debuff", "You gain 25% less Block from cards. Decreases by 1 at the end of your turn."),
    "INTANGIBLE": ("buff", "All damage and HP loss you take is reduced to 1. Decreases by 1 at the end of your turn."),
    "VULNERABLE": ("debuff", "You take 50% more damage from attacks. Decreases by 1 at the end of your turn."),
    "WEAK": ("debuff", "Your Attacks deal 25% less damage. Decreases by 1 at the end of your turn."),

    # --- debuffs ---
    "BIAS": ("debuff", "At the start of each turn, lose X Focus."),
    "CONFUSED": ("debuff", "The cost of every card you draw is randomized (0-3) for the rest of combat."),
    "CONSTRICTED": ("debuff", "At the end of your turn, take X damage."),
    "ENTANGLED": ("debuff", "You cannot play Attacks this turn."),
    "FASTING": ("debuff", "You gain X less Energy at the start of each turn."),
    "HEX": ("debuff", "Whenever you play a non-Attack card, shuffle a Dazed into your draw pile."),
    "LOSE_DEXTERITY": ("debuff", "At the end of your turn, lose X Dexterity."),
    "LOSE_STRENGTH": ("debuff", "At the end of your turn, lose X Strength."),
    "NO_BLOCK": ("debuff", "You cannot gain Block from cards this turn."),
    "NO_DRAW": ("debuff", "You cannot draw any more cards this turn."),
    "SURROUNDED": ("debuff", "You are surrounded: enemies you are not facing deal 50% more damage to you.",
                   "the engine treats the last enemy you targeted as the one you face."),
    "WRAITH_FORM": ("debuff", "At the end of your turn, lose X Dexterity."),

    # --- powers: flags ---
    "BARRICADE": ("power", "Your Block is not removed at the start of your turn."),
    "BLASPHEMER": ("power", "You die at the start of your next turn."),
    "CORRUPTION": ("power", "Skills cost 0. Whenever you play a Skill, Exhaust it."),
    "ELECTRO": ("power", "Your Lightning orbs hit ALL enemies."),
    "MASTER_REALITY": ("power", "Cards created during combat enter play Upgraded."),
    "PEN_NIB": ("power", "Your next Attack deals double damage."),
    "WRATH_NEXT_TURN": ("power", "You enter Wrath at the start of your next turn."),

    # --- powers: counters ---
    "AMPLIFY": ("power", "Your next X Power cards are played twice."),
    "BLUR": ("power", "Your Block is not removed at the start of your next X turns."),
    "BUFFER": ("power", "Prevent the next X times you would lose HP."),
    "COLLECT": ("power", "At the start of each of your next X turns, put a Miracle into your hand.",
                "the game puts in a Miracle+; the engine puts in a plain Miracle."),
    "DOUBLE_TAP": ("power", "Your next X Attacks are played twice."),
    "DUPLICATION": ("power", "Your next X cards are played twice."),
    "ECHO_FORM": ("power", "The first X cards you play each turn are played twice."),
    "FREE_ATTACK_POWER": ("power", "Your next X Attacks cost 0."),
    "MANTRA": ("power", "At 10 Mantra you enter Divinity and Mantra resets. (X so far)"),
    "REBOUND": ("power", "The next X cards you play this turn go on top of your draw pile instead of your discard pile."),

    # --- powers: intensity ---
    "ACCURACY": ("power", "Your Shivs deal X additional damage.", "not implemented (todo in the engine)."),
    "AFTER_IMAGE": ("power", "Whenever you play a card, gain X Block."),
    "BATTLE_HYMN": ("power", "At the start of each turn, add X Smite to your hand."),
    "BRUTALITY": ("power", "At the start of your turn, lose X HP and draw X cards."),
    "BURST": ("power", "Your next X Skills are played twice."),
    "COMBUST": ("power", "At the end of your turn, lose 1 HP per Combust played and deal X damage to ALL enemies."),
    "CREATIVE_AI": ("power", "At the start of your turn, add X random Power cards to your hand.",
                    "not implemented (todo in the engine)."),
    "DARK_EMBRACE": ("power", "Whenever a card is Exhausted, draw X cards."),
    "DEMON_FORM": ("power", "At the start of your turn, gain X Strength."),
    "DEVA": ("power", "At the start of your turn, gain Energy, then increase that gain by X."),
    "DEVOTION": ("power", "At the start of your turn, gain X Mantra."),
    "DRAW_CARD_NEXT_TURN": ("power", "Draw X additional cards next turn."),
    "ENERGIZED": ("power", "Gain X additional Energy next turn."),
    "ENVENOM": ("power", "Whenever you deal unblocked attack damage, apply X Poison to that enemy."),
    "ESTABLISHMENT": ("power", "Whenever a card is Retained, its cost is reduced by X for the rest of combat.",
                      "not implemented (todo in the engine)."),
    "EVOLVE": ("power", "Whenever you draw a Status card, draw X cards."),
    "FEEL_NO_PAIN": ("power", "Whenever a card is Exhausted, gain X Block."),
    "FIRE_BREATHING": ("power", "Whenever you draw a Status or Curse card, deal X damage to ALL enemies."),
    "FLAME_BARRIER": ("power", "When you are attacked, deal X damage back. Wears off at the start of your next turn."),
    "FOCUS": ("power", "Your orbs are X more effective. (Negative Focus weakens them.)"),
    "FORESIGHT": ("power", "At the start of your turn, Scry X.", "not implemented (todo in the engine)."),
    "HELLO_WORLD": ("power", "At the start of your turn, add a random Common card to your hand.",
                    "not implemented (the engine removes the power instead)."),
    "INFINITE_BLADES": ("power", "At the start of your turn, add X Shivs to your hand."),
    "JUGGERNAUT": ("power", "Whenever you gain Block, deal X damage to a random enemy."),
    "LIKE_WATER": ("power", "At the end of your turn, if you are in Calm, gain X Block."),
    "LOOP": ("power", "At the start of your turn, trigger the passive of your first orb X additional times.",
             "not implemented (todo in the engine)."),
    "MAGNETISM": ("power", "At the start of your turn, add X random Colorless cards to your hand.",
                  "not implemented (todo in the engine)."),
    "MAYHEM": ("power", "At the start of your turn, play the top X cards of your draw pile."),
    "METALLICIZE": ("power", "At the end of your turn, gain X Block."),
    "NEXT_TURN_BLOCK": ("power", "Gain X Block at the start of your next turn."),
    "NOXIOUS_FUMES": ("power", "At the start of your turn, apply X Poison to ALL enemies."),
    "OMEGA": ("power", "At the end of your turn, deal X damage to ALL enemies."),
    "PANACHE": ("power", "Every 5 cards you play, deal X damage to ALL enemies."),
    "PHANTASMAL": ("power", "For the next X turns, your Attacks deal double damage."),
    "PLATED_ARMOR": ("power", "At the end of your turn, gain X Block. Loses 1 stack whenever you take unblocked attack damage."),
    "RAGE": ("power", "Whenever you play an Attack this turn, gain X Block."),
    "REGEN": ("power", "At the end of your turn, heal X HP, then Regeneration decreases by 1."),
    "RITUAL": ("power", "At the end of your turn, gain X Strength."),
    "RUPTURE": ("power", "Whenever you lose HP from a card, gain X Strength."),
    "SADISTIC": ("power", "Whenever you apply a debuff to an enemy, deal X damage to it."),
    "STATIC_DISCHARGE": ("power", "Whenever you take unblocked attack damage, Channel X Lightning."),
    "THORNS": ("power", "When you are attacked, deal X damage back to the attacker."),
    "THOUSAND_CUTS": ("power", "Whenever you play a card, deal X damage to ALL enemies."),
    "TOOLS_OF_THE_TRADE": ("power", "At the start of your turn, draw X cards and discard X cards.",
                           "the engine draws but never asks you to discard."),
    "VIGOR": ("power", "Your next Attack deals X additional damage, then Vigor is removed."),
    "WAVE_OF_THE_HAND": ("power", "Whenever you gain Block this turn, apply X Weak to ALL enemies."),

    # --- durations / core stats ---
    "ARTIFACT": ("buff", "Negates the next X debuffs applied to you."),
    "DEXTERITY": ("buff", "You gain X additional Block from cards. (Negative Dexterity reduces it.)"),
    "EQUILIBRIUM": ("power", "Your hand is Retained for the next X turns.",
                    "the engine retains the hand but does not force Ethereal cards to stay."),
    "STRENGTH": ("buff", "Your Attacks deal X additional damage per hit. (Negative Strength reduces it.)"),
    "THE_BOMB": ("power", "At the end of 3 turns, deal X damage to ALL enemies.",
                 "not implemented — the engine stores the damage but never detonates it."),
}

# Flag-only monster statuses — `isBooleanPower` in MonsterStatusEffects.h.
MONSTER_FLAGS = {
    "ASLEEP", "BARRICADE", "MINION", "MINION_LEADER", "PAINFUL_STABS", "REGROW",
    "SHIFTING", "STASIS",
}

# Hand-authored, keyed by MonsterStatus enum name. Phrased from the player's side —
# "this enemy" — because that is how the encoder renders them.
MONSTER_STATUS = {
    # --- things you apply to an enemy ---
    "ARTIFACT": ("buff", "Negates the next X debuffs applied to this enemy."),
    "BLOCK_RETURN": ("debuff", "Whenever you attack this enemy, you gain X Block.",
                     "inert — nothing in the engine applies it."),
    "CHOKED": ("debuff", "Whenever you play a card this turn, this enemy loses X HP."),
    "CORPSE_EXPLOSION": ("debuff", "When this enemy dies, deal damage equal to X times its Max HP to ALL enemies."),
    "LOCK_ON": ("debuff", "Lightning and Dark orbs deal 50% more damage to this enemy. Decreases by 1 each round."),
    "MARK": ("debuff", "Whenever you play Pressure Points, this enemy loses X HP."),
    "METALLICIZE": ("buff", "At the end of its turn, this enemy gains X Block."),
    "PLATED_ARMOR": ("buff", "At the end of its turn, this enemy gains X Block. Loses 1 stack whenever it takes unblocked attack damage."),
    "POISON": ("debuff", "At the start of its turn, this enemy loses X HP, then Poison decreases by 1."),
    "REGEN": ("buff", "At the start of its turn, this enemy heals X HP."),
    "SHACKLED": ("debuff", "This enemy has lost X Strength; it regains that Strength at the end of its turn."),
    "STRENGTH": ("buff", "This enemy's attacks deal X additional damage per hit. (Negative Strength reduces it.)"),
    "VULNERABLE": ("debuff", "This enemy takes 50% more damage from attacks. Decreases by 1 each round."),
    "WEAK": ("debuff", "This enemy's attacks deal 25% less damage. Decreases by 1 each round."),

    # --- innate powers (one per monster) ---
    "ANGRY": ("power", "Whenever this enemy takes attack damage, it gains X Strength."),
    "BEAT_OF_DEATH": ("power", "Whenever you play a card, you take X damage."),
    "CURIOSITY": ("power", "Whenever you play a Power card, this enemy gains X Strength."),
    "CURL_UP": ("power", "The first time this enemy takes attack damage, it gains X Block and loses this power."),
    "ENRAGE": ("power", "Whenever you play a Skill, this enemy gains X Strength."),
    "FADING": ("power", "This enemy dies in X turns."),
    "FLIGHT": ("power", "Attack damage to this enemy is halved. Each hit removes 1 stack; at 0 it is stunned for a turn."),
    "GENERIC_STRENGTH_UP": ("power", "At the end of each round, this enemy gains X Strength."),
    "INTANGIBLE": ("power", "All damage this enemy takes is reduced to 1.",
                   "the engine always decrements it at the end of the round, unlike the game."),
    "MALLEABLE": ("power", "Whenever this enemy takes attack damage, it gains X Block; X grows by 1 per hit and resets to 3 each turn."),
    "MODE_SHIFT": ("power", "After taking X more damage, this enemy shifts to its defensive mode."),
    "RITUAL": ("power", "At the end of each round, this enemy gains X Strength (skipping the round it was applied)."),
    "SLOW": ("power", "This enemy takes 10% more damage for each card you played this turn. Resets each round."),
    "SPORE_CLOUD": ("power", "When this enemy dies, you gain X Vulnerable.", "the engine always applies 2."),
    "THIEVERY": ("power", "This enemy steals X gold whenever it attacks you."),
    "THORNS": ("power", "Whenever you attack this enemy, you take X damage."),
    "TIME_WARP": ("power", "Whenever you play 12 cards, this enemy gains 2 Strength and your turn ends. (X so far)"),
    "INVINCIBLE": ("power", "This enemy can lose at most X more HP this turn."),
    "REACTIVE": ("power", "Whenever this enemy takes attack damage, it changes its intent."),
    "SHARP_HIDE": ("power", "Whenever you play an Attack, you take X damage."),

    # --- boolean powers ---
    "ASLEEP": ("power", "This enemy is asleep: it does not act, and waking it removes its Metallicize."),
    "BARRICADE": ("power", "This enemy's Block is not removed at the start of its turn."),
    "MINION": ("power", "This enemy is a minion; it flees when its leader dies."),
    "MINION_LEADER": ("power", "Killing this enemy ends the fight."),
    "PAINFUL_STABS": ("power", "Whenever this enemy deals unblocked attack damage, a Wound is shuffled into your discard pile."),
    "REGROW": ("power", "When this enemy dies, it revives with full HP."),
    "SHIFTING": ("power", "Whenever this enemy takes damage, it loses that much Strength until the end of its turn."),
    "STASIS": ("power", "This enemy holds a card of yours; it returns to your discard pile when the enemy dies."),
}

_CONNECTORS = {"of", "the", "in", "a", "and", "to"}
# Display names the header's title-casing gets wrong.
_NAME_OVERRIDES = {"CREATIVE_AI": "Creative AI"}


def _strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def _quoted_list(block: str) -> list[str]:
    return re.findall(r'"([^"]*)"', block)


def _prettify(name: str) -> str:
    """'Wave Of The Hand' -> 'Wave of the Hand' (same rule as the potion pipeline)."""
    words = name.split()
    return " ".join(
        w if i == 0 or w.lower() not in _CONNECTORS else w.lower()
        for i, w in enumerate(words)
    )


def parse_enum(header: str, enum_name: str, strings_array: str) -> list[tuple[str, str]]:
    """-> [(ENUM_NAME, 'Display Name')] in enum order.

    The enum body is the authority on order; the display-name array is index-aligned to
    it. (Don't be tempted by `monsterStatusEnumStrings` — that one is misordered in the
    header: REACTIVE sits after PAINFUL_STABS instead of after INVINCIBLE.)
    """
    text = _strip_comments(header)
    body = re.search(rf"enum class {enum_name}\s*:\s*[\w:]+\s*\{{(.*?)\}};", text, re.S).group(1)
    ids = re.findall(r"\b([A-Z][A-Z0-9_]*)\b", body)
    names = _quoted_list(re.search(rf"{strings_array}\[\]\s*=?\s*\{{(.*?)\}};", text, re.S).group(1))
    if len(ids) != len(names):
        raise SystemExit(f"{enum_name}: {len(ids)} enum values but {len(names)} display names")
    return list(zip(ids, names))


def build_section(pairs, authored: dict, flags: set[str], owner: str) -> dict[str, dict]:
    ids = [i for i, _ in pairs if i != "INVALID"]
    missing = [i for i in ids if i not in authored]
    extra = sorted(set(authored) - set(ids))
    if missing:
        raise SystemExit(f"{owner} statuses with no authored text:\n  " + "\n  ".join(missing))
    if extra:
        raise SystemExit(f"Authored text for non-existent {owner} statuses:\n  " + "\n  ".join(extra))
    bad_flags = sorted(flags - set(ids))
    if bad_flags:
        raise SystemExit(f"{owner} flag list names non-existent statuses:\n  " + "\n  ".join(bad_flags))

    out: dict[str, dict] = {}
    for sid, display in pairs:
        if sid == "INVALID":
            continue
        kind, text, *note = authored[sid]
        out[sid] = {
            "name": _NAME_OVERRIDES.get(sid, _prettify(display)),
            "owner": owner,
            "kind": kind,
            "stacks": sid not in flags,
            "text": text,
            "engine_note": note[0] if note else None,
        }
    return out


def main() -> None:
    player_pairs = parse_enum(PLAYER_H.read_text(encoding="utf-8"), "PlayerStatus", "playerStatusStrings")
    monster_pairs = parse_enum(MONSTER_H.read_text(encoding="utf-8"), "MonsterStatus", "enemyStatusStrings")

    data = {
        "PLAYER": build_section(player_pairs, PLAYER_STATUS, PLAYER_FLAGS, "PLAYER"),
        "MONSTER": build_section(monster_pairs, MONSTER_STATUS, MONSTER_FLAGS, "MONSTER"),
    }

    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(data['PLAYER'])} player + {len(data['MONSTER'])} monster statuses "
          f"-> {OUT.relative_to(REPO)}")
    for owner, section in data.items():
        by_kind: dict[str, int] = {}
        for s in section.values():
            by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
        notes = [sid for sid, s in section.items() if s["engine_note"]]
        print(f"{owner}: {dict(sorted(by_kind.items()))}, {len(notes)} engine notes")


if __name__ == "__main__":
    main()
