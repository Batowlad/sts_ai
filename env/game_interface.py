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


from game_data.card_data.card_text import describe_card


class GameInterface:
    def __init__(self):
        self.gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 42, 0)
        self.bc = sts.BattleContext()
        self.map = sts.SpireMap(42, 0, 0, False) #CHANGE 3rd value based on act (add later)!!!!!!!!!!!!!!
        self.bc_initiated = False

    def legal_actions(self):
        if self.gc.screen_state == sts.ScreenState.BATTLE:
            actions_list = sts.get_legal_actions(self.bc)
            return actions_list
        else:
            actions_list = sts.GameAction.get_all_actions_in_state(self.gc)
            print(actions_list) # debugging
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
            if self.bc_initiated == False:
                self.bc.init(self.gc)
                self.bc_initiated = True
            if self.bc.outcome == sts.BattleOutcome.PLAYER_VICTORY or self.bc.outcome == sts.BattleOutcome.PLAYER_LOSS:
                self.bc.exit_battle(self.gc)
                self.bc_initiated = False

        elif self.gc.screen_state == sts.ScreenState.EVENT_SCREEN:
            # try:
            #     self.gc.chooseEventOption(action.idx1)
            # # OR 
            # except:
                sts.GameAction(idx1=action).execute(self.gc)
        
        elif self.gc.screen_state == sts.ScreenState.MAP_SCREEN:
            sts.GameAction(idx1=action).execute(self.gc)

    
    def describe_card(self, id):
        card = sts.Card(id)
        return describe_card(card.id) #ADD UPGRADE READ CAPABILITY


    def view_deck(self):
        return self.gc.deck


    def encode_state(self) -> str:
        cur_screen = self.gc.screen_state
        cur_hp = self.gc.cur_hp
        max_hp = self.gc.max_hp
        gold = self.gc.gold
        potion_count = self.gc.potion_count
        potion_capacity = self.gc.potion_capacity

        map_x = self.gc.cur_map_node_x
        map_y = self.gc.cur_map_node_y

        deck = self.gc.deck
        relics = self.gc.relics
        potions = self.gc.potions

        # BATTLE LIVE VIEW
        player_view = self.bc.player
        monsters_view = self.bc.monsters
        cards_view = self.bc.cards

        # return f"Current screen: {cur_screen}, HP: {cur_hp}/{max_hp}, Gold amount: {gold}, Potion count: {potion_count}, Current map node: ({map_x}, {map_y}, Deck: {deck})"
        if self.gc.screen_state == sts.ScreenState.BATTLE:
            return f"HP: {cur_hp}/{max_hp}, Player: {player_view}, Monsters: {monsters_view}, Cards: {cards_view}, Deck: {deck}" # VERY VERY LIKELY TO BE EDITED
        elif self.gc.screen_state == sts.ScreenState.MAP_SCREEN:
            return f"{self.view_map()}\nCurrent map node: ({map_x}, {map_y}), HP: {cur_hp}/{max_hp}, Gold amount: {gold}"
        elif self.gc.screen_state == sts.ScreenState.EVENT_SCREEN:
            return f"HP: {cur_hp}/{max_hp}, Gold amount: {gold}, Deck: {deck}"
        elif self.gc.screen_state == sts.ScreenState.REST_ROOM:
            return f"HP: {cur_hp}/{max_hp}, Deck: {deck}"
        elif self.gc.screen_state == sts.ScreenState.CARD_SELECT:
            return f"Deck: {deck}"
        elif self.gc.screen_state == sts.ScreenState.SHOP_ROOM:
            return f"Gold amount: {gold}, potion slots: {potion_count}/{potion_capacity}"
        elif self.gc.screen_state == sts.ScreenState.BOSS_RELIC_REWARDS:
            return 1