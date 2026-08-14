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


########################## MAKING OTHER FOLDERS VISIBLE #####################
if BUILD_DIR not in sys.path:
    sys.path.insert(0, BUILD_DIR)
# Scripts run from inside env/ (e.g. `python test.py`) only get env/ on sys.path,
# so top-level packages like game_data are invisible without this.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# ...and the mirror case: imported as `env.game_interface` from the repo root
# (tests/, data/, eval/), env/ itself is not on sys.path, so the flat sibling
# imports below (`event_options`) would not resolve.
if str(_REPO_ROOT / "env") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "env"))
if hasattr(os, "add_dll_directory") and os.path.isdir(MINGW_BIN):
    os.add_dll_directory(MINGW_BIN)
#############################################################################


import slaythespire as sts  # type: ignore

from event_options import describe_event_option
from game_data.card_data import card_text
from game_data.card_data.card_text import describe_card
from game_data.potion_data import potion_text
from game_data.relic_data import relic_text

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


# Short display names for action lines. The full effect text belongs in the
# glossaries the state encoder builds, not in every legal-action line.
def _enum_name(enum_val) -> str:
    """Fallback for ids the game_data tables don't cover (non-Ironclad pools):
    RelicId.BLOOD_VIAL -> 'Blood Vial'."""
    return str(enum_val).split(".")[-1].replace("_", " ").title()


def _card_name(card) -> str:
    """A Card -> 'Bash' / 'Bash+' (reward and shop cards can roll upgraded)."""
    data = card_text.get(card)
    name = data["name"] if data else _enum_name(getattr(card, "id", card))
    return name + ("+" if getattr(card, "upgraded", False) else "")


def _relic_name(relic) -> str:
    data = relic_text.get(relic)
    return data["name"] if data else _enum_name(relic)


def _potion_name(potion) -> str:
    data = potion_text.get(potion)
    return data["name"] if data else _enum_name(potion)


def _describe_reward(a, gc):
    """REWARDS screen — dispatch on rewards_action_type, then idx1/idx2 index
    into the matching list of `gc.rewards_container`."""
    rt = a.rewards_action_type
    r = gc.rewards_container

    if rt == sts.RewardsActionType.CARD:
        if a.idx2 == 5:
            # not enumerated by get_all_actions_in_state, but constructible
            return "skip the card reward (+2 max HP with Singing Bowl)"
        bundles = r["cards"]
        if a.idx1 < len(bundles) and a.idx2 < len(bundles[a.idx1]):
            return f"take card: {_card_name(bundles[a.idx1][a.idx2])}"
        return f"take card {a.idx2} of reward bundle {a.idx1}"

    if rt == sts.RewardsActionType.GOLD:
        gold = r["gold"]
        # Engine quirk: getAllRewardActions enumerates every gold pile with
        # idx1=0, so two piles show up as two identical lines (and executing
        # either takes pile 0). Harmless, but don't read the duplicate as a bug.
        if a.idx1 < len(gold):
            return f"take {gold[a.idx1]} gold"
        return "take the gold"

    if rt == sts.RewardsActionType.RELIC:
        relics = r["relics"]
        if a.idx1 >= len(relics):
            return f"take relic {a.idx1}"
        text = f"take relic: {_relic_name(relics[a.idx1])}"
        if r["sapphire_key"] and a.idx1 == len(relics) - 1:
            text += " (forfeits the sapphire key)"
        return text

    if rt == sts.RewardsActionType.POTION:
        potions = r["potions"]
        if a.idx1 < len(potions):
            return f"take potion: {_potion_name(potions[a.idx1])}"
        return f"take potion {a.idx1}"

    if rt == sts.RewardsActionType.KEY:
        # sapphire wins if both are somehow set — mirrors executeRewardsAction
        if r["sapphire_key"]:
            suffix = " (forfeits the relic)" if r["relics"] else ""
            return f"take the sapphire key{suffix}"
        return "take the emerald key"

    if rt == sts.RewardsActionType.SKIP:
        return "leave the rewards screen"

    return f"{rt} idx1={a.idx1} idx2={a.idx2}"


def _describe_shop(a, gc):
    """SHOP_ROOM screen — same dispatch, indices point into `gc.shop`."""
    rt = a.rewards_action_type
    s = gc.shop
    i = a.idx1

    if rt == sts.RewardsActionType.CARD and i < len(s["cards"]):
        return f"buy card: {_card_name(s['cards'][i])} ({s['card_prices'][i]} gold)"

    if rt == sts.RewardsActionType.RELIC and i < len(s["relics"]):
        return f"buy relic: {_relic_name(s['relics'][i])} ({s['relic_prices'][i]} gold)"

    if rt == sts.RewardsActionType.POTION and i < len(s["potions"]):
        return f"buy potion: {_potion_name(s['potions'][i])} ({s['potion_prices'][i]} gold)"

    if rt == sts.RewardsActionType.CARD_REMOVE:
        return f"pay {s['remove_cost']} gold to remove a card from the deck"

    if rt == sts.RewardsActionType.SKIP:
        return "leave the shop"

    return f"{rt} idx1={a.idx1} idx2={a.idx2}"


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
        if a.idx1 == 3:
            return "skip the boss relics"
        return f"take boss relic: {_relic_name(gc.boss_relics[a.idx1])}"
    if ss == sts.ScreenState.CARD_SELECT:
        return f"select card {a.idx1}"
    if ss == sts.ScreenState.MAP_SCREEN:
        return f"move to map node x={a.idx1}"
    if ss == sts.ScreenState.REWARDS:
        return _describe_reward(a, gc)
    if ss == sts.ScreenState.SHOP_ROOM:
        return _describe_shop(a, gc)
    return f"{ss} option {a.idx1}"

# TODO: GameInterface class — step(), legal_actions(), reset(), run-combat-via-Agent, etc.


class GameInterface:
    def __init__(self):
        self.gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 42, 0)
        self.bc = sts.BattleContext()
        self.map = sts.SpireMap(42, 0, 1, False)
        self.bc_initiated = False

    def legal_actions(self):
        if self.gc.screen_state == sts.ScreenState.BATTLE:
            actions_list = sts.get_legal_actions(self.bc)
            return actions_list
        else:
            actions_list = sts.GameAction.get_all_actions_in_state(self.gc)
            # print(actions_list) # debugging
            decoded_actions = []
            for x in actions_list:
                action = describe(x, self.gc)
                decoded_actions.append(action)
            return decoded_actions
        
    def reset(self):
        self.gc = new_game() # to be tested

    def view_map(self):
        return self.map.__repr__()

    def step(self, action):
        if self.gc.screen_state == sts.ScreenState.BATTLE: # WHEN IN BATTLE
            # gc sits on the BATTLE screen for the whole fight; every decision
            # goes through the BattleContext instead (see docs, "Combat").
            if not self.bc_initiated:
                self.bc.init(self.gc)
                self.bc_initiated = True

            if self.bc.outcome != sts.BattleOutcome.UNDECIDED:
                raise RuntimeError(
                    f"battle already over ({self.bc.outcome}) — no action to take"
                )

            if isinstance(action, sts.Action):
                combat_action = action
            else:
                # `action` is an index into legal_actions() / the same order the
                # policy was shown.
                actions_list = sts.get_legal_actions(self.bc)
                if not actions_list:
                    # Only happens for the card-select tasks the engine doesn't
                    # implement (Hologram/Meditate/Nightmare/Recycle/Setup/Seek).
                    raise RuntimeError(
                        f"no legal combat actions while the battle is undecided "
                        f"(input_state={self.bc.input_state}, "
                        f"task={self.bc.card_select_info.task})"
                    )
                if not isinstance(action, int) or not 0 <= action < len(actions_list):
                    raise IndexError(
                        f"action {action!r} is not a valid index into the "
                        f"{len(actions_list)} legal combat actions"
                    )
                combat_action = actions_list[action]

            # Applies the action and runs the engine (monster turns, shuffles,
            # ...) up to the next decision point. Raises ValueError if illegal.
            combat_action.execute(self.bc)

        else: # FOR ALL THE OTHER SCREENS
            actions_list = sts.GameAction.get_all_actions_in_state(self.gc)
            if not actions_list:
                raise RuntimeError(f"no legal actions on {self.gc.screen_state}")
            if not isinstance(action, int) or not 0 <= action < len(actions_list):
                raise IndexError(
                    f"action {action!r} is not a valid index into the "
                    f"{len(actions_list)} legal actions on {self.gc.screen_state}"
                )
            actions_list[action].execute(self.gc)

        # CHECK FOR BATTLE SCREEN TO INIT BATTLE
        if self.gc.screen_state == sts.ScreenState.BATTLE: # WHEN SWITCHING TO BATTLE
            if self.bc_initiated == False:
                self.bc.init(self.gc)
                self.bc_initiated = True
            if self.bc.outcome != sts.BattleOutcome.UNDECIDED:
                self.bc.exit_battle(self.gc)
                self.bc_initiated = False

    
    def card_describe(self, card, upgraded=None):
        # card_text.describe_card takes a Card, a CardId, or a plain id string.
        return describe_card(card, upgraded)


    def view_deck(self):
        return self.gc.deck