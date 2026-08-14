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


##################### MAKING OTHER FOLDERS VISIBLE ##########################
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


class GameInterface:
    def __init__(self):
        self.gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 42, 0)
        self.bc = sts.BattleContext()
        self.map = sts.SpireMap(42, 0, 1, False)
        self.bc_initiated = False

    def legal_actions(self):
        if self.gc.screen_state == sts.ScreenState.BATTLE:
            actions_list = sts.get_legal_actions(self.bc)
            # Same order as the list step() indexes into, so the position a
            # description sits at is the number to pass back.
            return [describe_battle(a, self.bc) for a in actions_list]
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

    def view_relics(self):
        return self.gc.relics

    def view_potions(self):
        return self.gc.potions

    
###############################################################
############ OTHER STUFF THAT MAKES IT WORK ###################
###############################################################


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

# Potions the engine asks a target for (mirrors potionRequiresTarget in
# constants/Potions.h). potion_data.json carries the same flag, but only over the
# Ironclad pool — Poison Potion isn't in it, and the engine still targets it.
TARGETED_POTIONS = {
    sts.Potion.FEAR_POTION,
    sts.Potion.FIRE_POTION,
    sts.Potion.POISON_POTION,
    sts.Potion.WEAK_POTION,
}


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


def _monster_name(bc, idx) -> str:
    """'Jaw Worm (enemy 0)' — the index stays because same-name enemies are the
    norm (3 Cultists, 2 Louses) and the policy has to say *which* one."""
    monsters = bc.monsters
    if 0 <= idx < len(monsters):
        # Monster.name is the raw id string ('JAW_WORM'), not a display name.
        return f"{_enum_name(monsters[idx].name)} (enemy {idx})"
    return f"enemy {idx}"


def _pile_card(cards, idx) -> str:
    """Name the card an index points at, for any of the combat piles."""
    return _card_name(cards[idx]) if 0 <= idx < len(cards) else f"card {idx}"


def _describe_card_select(a, bc):
    """CARD_SELECT input state — the index is into a pile the *task* chooses, so
    dispatch on the task and name the card.

    (The engine's own describe() prints the task name and gives up here: "TODO we
    don't know if it's selecting from hand or discard". The piles below come from
    isValidSingleCardSelectAction in src/sim/search/Action.cpp.)
    """
    t = sts.CardSelectTask
    info = bc.card_select_info
    task = info.task

    if a.action_type == sts.ActionType.MULTI_CARD_SELECT:
        # Only EXHAUST_MANY and GAMBLE are multi-selects, both out of the hand.
        verb = "discard" if task == t.GAMBLE else "exhaust"
        hand = bc.cards.hand
        picks = ", ".join(_pile_card(hand, i) for i in a.selected_idxs)
        if not picks:
            return f"{verb} nothing"
        return f"{verb} {picks}" + (" and draw that many" if task == t.GAMBLE else "")

    idx = a.select_idx

    if task in (t.CODEX, t.DISCOVERY):
        return f"add {_pile_card(info.cards, idx)} to your hand"

    if task == t.EXHUME:
        return f"return {_pile_card(bc.cards.exhaust_pile, idx)} from the exhaust pile"

    if task in (t.HOLOGRAM, t.LIQUID_MEMORIES_POTION, t.MEDITATE):
        return f"return {_pile_card(bc.cards.discard_pile, idx)} from the discard pile"

    if task == t.HEADBUTT:
        card = _pile_card(bc.cards.discard_pile, idx)
        return f"put {card} from the discard pile on top of the draw pile"

    if task in (t.SEEK, t.SECRET_TECHNIQUE, t.SECRET_WEAPON):
        return f"take {_pile_card(bc.cards.draw_pile, idx)} from the draw pile"

    # Everything left selects out of the hand.
    card = _pile_card(bc.cards.hand, idx)

    if task == t.ARMAMENTS:
        return f"upgrade {card}"
    if task == t.DUAL_WIELD:
        return f"copy {card}"
    if task == t.EXHAUST_ONE:
        return f"exhaust {card}"
    if task == t.RECYCLE:
        return f"exhaust {card} and gain its cost as energy"
    if task == t.FORETHOUGHT:
        return f"put {card} on the bottom of the draw pile"
    if task in (t.SETUP, t.WARCRY):
        return f"put {card} on top of the draw pile"
    if task == t.NIGHTMARE:
        return f"choose {card} for Nightmare"

    return f"{_enum_name(task)}: {card}"


def describe_battle(a, bc):
    """BATTLE screen — the combat twin of describe(), dispatching on action_type.

    Same job as the engine's `a.describe(bc)` ("{ use card (0) Strike -> (0) Jaw
    Worm }"), but phrased like the out-of-combat lines and with the card named in
    every card-select task.
    """
    at = a.action_type

    if at == sts.ActionType.END_TURN:
        return "end turn"

    if at == sts.ActionType.CARD:
        hand = bc.cards.hand
        i = a.source_idx
        # Untargeted cards are enumerated with target_idx 0, which is also a real
        # monster index — the card itself is what says whether it aims.
        if 0 <= i < len(hand) and hand[i].requires_target:
            return f"play {_pile_card(hand, i)} on {_monster_name(bc, a.target_idx)}"
        return f"play {_pile_card(hand, i)}"

    if at == sts.ActionType.POTION:
        potions = bc.potions
        i = a.source_idx
        if not 0 <= i < len(potions):
            return f"use the potion in slot {i}"
        name = _potion_name(potions[i])
        # A discard is encoded as target -1, which reads back as 8191 (13 bits).
        # Targeted potions also land here when nothing is targetable, and Fairy in
        # a Bottle is only ever discardable.
        if a.target_idx > 5:
            return f"discard {name}"
        if potions[i] in TARGETED_POTIONS:
            return f"drink {name} on {_monster_name(bc, a.target_idx)}"
        return f"drink {name}"

    if at in (sts.ActionType.SINGLE_CARD_SELECT, sts.ActionType.MULTI_CARD_SELECT):
        return _describe_card_select(a, bc)

    return repr(a)


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


