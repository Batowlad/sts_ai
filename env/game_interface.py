"""Wraps the sts_lightspeed `slaythespire` pybind module.

Centralizes the import shim (build dir on sys.path + mingw DLL dir) so the rest
of the project can just `from env.game_interface import sts`.
"""
import os
import sys
from pathlib import Path

# Auto-detected relative to this repo, so a fresh clone works on any machine /
# any path with no edits. Override with the env vars only if your layout differs.
_REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = os.environ.get(
    "STS_BUILD_DIR", str(_REPO_ROOT / "sts_lightspeed" / "cmake-build-mingw")
)
# Only needed on Windows when the interpreter is NOT MSYS2's mingw64 python
# (with that one, the mingw DLLs sit next to python.exe and resolve for free).
MINGW_BIN = os.environ.get("STS_MINGW_BIN", r"C:\msys64\mingw64\bin")

if BUILD_DIR not in sys.path:
    sys.path.insert(0, BUILD_DIR)
if hasattr(os, "add_dll_directory") and os.path.isdir(MINGW_BIN):
    os.add_dll_directory(MINGW_BIN)

import slaythespire as sts  # noqa: E402

from event_options import describe_event_option  # noqa: E402

REST_ROOM_OPTIONS = {
    0: "rest (heal 30% max HP)",
    1: "smith (upgrade a card)",
    2: "take the ruby key",
    3: "lift (Girya: +1 strength)",
    4: "toke (Peace Pipe: remove a card)",
    5: "dig (Shovel: obtain a relic)",
    6: "skip",
}

TREASURE_ROOM_OPTIONS = {0: "open the chest", 1: "skip the chest"}


def new_game(character=None, seed: int = 42, ascension: int = 0):
    """Create a fresh GameContext (defaults to Ironclad)."""
    if character is None:
        character = sts.CharacterClass.IRONCLAD
    return sts.GameContext(character, seed, ascension)

def describe(a, gc):
    if a.is_potion_action:
        verb = "discard" if a.is_potion_discard else "drink"
        return f"{verb} potion in slot {a.idx1} ({gc.potions[a.idx1]})"
    ss = gc.screen_state
    if ss == sts.ScreenState.EVENT_SCREEN:
        return f"[{gc.cur_event_name}] {describe_event_option(gc, a.idx1)}"
    if ss == sts.ScreenState.REST_ROOM:
        return REST_ROOM_OPTIONS.get(a.idx1, f"option {a.idx1}")
    if ss == sts.ScreenState.TREASURE_ROOM:
        return TREASURE_ROOM_OPTIONS.get(a.idx1, f"option {a.idx1}")
    if ss == sts.ScreenState.BOSS_RELIC_REWARDS:
        return "skip the boss relics" if a.idx1 == 3 else f"take boss relic {a.idx1}"
    if ss == sts.ScreenState.CARD_SELECT:
        return f"select card {a.idx1}"
    if ss == sts.ScreenState.MAP_SCREEN:
        return f"move to map node x={a.idx1}"
    if ss in (sts.ScreenState.REWARDS, sts.ScreenState.SHOP_ROOM):
        return f"{a.rewards_action_type} idx1={a.idx1} idx2={a.idx2}"
    return f"{ss} option {a.idx1}"

# TODO: GameInterface class — step(), legal_actions(), reset(), run-combat-via-Agent, etc.


class GameInterface:
    def __init__(self):
        self.gc = new_game()
        self.bc = sts.BattleContext()

    def legal_actions(self):
        if self.gc.screen_state == sts.ScreenState.BATTLE:
            actions_list = sts.get_legal_actions(self.bc)
            return actions_list
        else:
            actions_list =  sts.GameAction.get_all_actions_in_state(self.gc)
            return describe(actions_list, self.gc)
        


if __name__ == "__main__":
    gi = GameInterface()
    for a in sts.GameAction.get_all_actions_in_state(gi.gc):
        print(describe(a, gi.gc))