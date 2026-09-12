"""Wraps the sts_lightspeed `slaythespire` pybind module.

Centralizes the import shim (build dir on sys.path + mingw DLL dir) so the rest
of the project can just `from env.game_interface import sts`.
"""
import os
import sys
from functools import cache
from pathlib import Path

# Auto-detected from the repo root; override with the env vars if your layout differs.
_REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = os.environ.get(
    "STS_BUILD_DIR", str(_REPO_ROOT / "sts_lightspeed" / "cmake-build-mingw")
)
# Only needed on Windows when the interpreter is not MSYS2's mingw64 python
# (that one ships the mingw DLLs next to python.exe).
MINGW_BIN = os.environ.get("STS_MINGW_BIN", r"C:\msys64\mingw64\bin")


##################### MAKING OTHER FOLDERS VISIBLE ##########################
if BUILD_DIR not in sys.path:
    sys.path.insert(0, BUILD_DIR)
# Scripts run from inside env/ only get env/ on sys.path, so game_data needs this.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Mirror case: imported from the repo root, env/ is not on sys.path, so the flat
# sibling imports below (`event_options`) would not resolve.
if str(_REPO_ROOT / "env") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "env"))
if hasattr(os, "add_dll_directory") and os.path.isdir(MINGW_BIN):
    os.add_dll_directory(MINGW_BIN)
#############################################################################


import slaythespire as sts  # type: ignore

from event_options import describe_event_option
from game_types import ActionOption
from render import render_action_options
from game_data.card_data import card_text
from game_data.card_data.card_text import describe_card
from game_data.potion_data import potion_text
from game_data.potion_data.potion_text import describe_potion, potion_glossary
from game_data.relic_data import relic_text
from game_data.relic_data.relic_text import describe_relic, relic_glossary
from game_data.status_data import status_text
from game_data.status_data.status_text import describe_status, status_glossary

import string #to check if its a special char in view_map()

class GameInterface:
    def __init__(self):
        self.gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 42, 0)
        self.bc = sts.BattleContext()
        self.map = sts.SpireMap(42, 0, 1, False)
        self.bc_initiated = False

    def legal_action_options(self):
        """The legal choices as typed `ActionOption`s — the version to use from code.

        `observe` is imported here rather than at module scope because it imports *this*
        module for `sts` and the describers; a top-level import would be a cycle. After
        the first call it is a dict lookup in `sys.modules`.
        """
        from observe import build_action_options

        return build_action_options(self)

    def observe(self):
        """A typed, detached snapshot of the current decision point."""
        from observe import build_observation

        return build_observation(self)

    def legal_actions(self):
        """The legal choices as the one prompt-ready line the policy reads.

        A thin render over `legal_action_options()`; the numbering it prints is what
        `step()` and `env/action_parser.py` consume.
        """
        return render_action_options(self.legal_action_options(), _tail(self.gc.screen_state))


    def reset(self):
        self.gc = new_game()

    def view_map(self):
        map = self.map.__repr__()
        cur_y = self.gc.cur_map_node_y

        if cur_y == -1:
            return map
        if cur_y == 0:
            cur_index = -1
        else:
            default = -1
            cur_index = [default-(2*(x+1)) for x in range(cur_y)][-1]

        map_list = str(map).splitlines()

        cur_line = map_list[cur_index]
        line_list = list(cur_line)
        occurence = 0
        for i in range(len(line_list)):
            if line_list[i].isalpha() or line_list[i] in string.punctuation:
                occurence += 1
                if occurence == self.gc.cur_map_node_x:
                    line_list[i] = line_list[i].replace(line_list[i], "X")
                    break

        map_list[cur_index] = "".join(line_list)
        map = "\n".join(map_list)
        return map

    def _resolve_action(self, action, in_combat: bool):
        """Whatever `step()` was handed -> the engine action to execute.

        An engine `Action` / `GameAction` passes straight through. An `ActionOption` is
        rebuilt from its bits, not its index: the index only means something for the
        step that produced it, while the bits are the engine's own packing of the
        decision. Anything else is treated as an index into `legal_actions()`.
        """
        engine_cls = sts.Action if in_combat else sts.GameAction
        if isinstance(action, engine_cls):
            return action

        if isinstance(action, ActionOption):
            screen = _tail(self.gc.screen_state)
            if action.screen != screen:
                raise ValueError(
                    f"{action.key!r} was enumerated on {action.screen}, but the game is "
                    f"on {screen} — its bits would decode as a different decision"
                )
            if action.bits is None:
                raise ValueError(f"{action.key!r} carries no bits to replay")
            engine_action = engine_cls.from_bits(action.bits)
            if not engine_action.is_valid(self.bc if in_combat else self.gc):
                raise ValueError(f"{action.key!r} is not legal in the current state")
            return engine_action

        # `action` is an index into legal_actions().
        if in_combat:
            actions_list = sts.get_legal_actions(self.bc)
            if not actions_list:
                # Only for card-select tasks the engine doesn't implement
                # (Hologram/Meditate/Nightmare/Recycle/Setup/Seek).
                raise RuntimeError(
                    f"no legal combat actions while the battle is undecided "
                    f"(input_state={self.bc.input_state}, "
                    f"task={self.bc.card_select_info.task})"
                )
            which = "legal combat actions"
        else:
            actions_list = sts.GameAction.get_all_actions_in_state(self.gc)
            if not actions_list:
                raise RuntimeError(f"no legal actions on {self.gc.screen_state}")
            which = f"legal actions on {self.gc.screen_state}"

        if not isinstance(action, int) or not 0 <= action < len(actions_list):
            raise IndexError(
                f"action {action!r} is not a valid index into the "
                f"{len(actions_list)} {which}"
            )
        return actions_list[action]

    def step(self, action):
        """Take one action: an index into `legal_actions()`, an `ActionOption`, or an
        engine `Action` / `GameAction`."""
        in_combat = self.gc.screen_state == sts.ScreenState.BATTLE
        if in_combat: # WHEN IN BATTLE
            # gc stays on the BATTLE screen all fight; decisions go through bc.
            if not self.bc_initiated:
                self.bc.init(self.gc)
                self.bc_initiated = True

            if self.bc.outcome != sts.BattleOutcome.UNDECIDED:
                raise RuntimeError(
                    f"battle already over ({self.bc.outcome}) — no action to take"
                )

        # Runs the engine to the next decision point; ValueError if illegal.
        self._resolve_action(action, in_combat).execute(self.bc if in_combat else self.gc)

        # CHECK FOR BATTLE SCREEN TO INIT BATTLE
        if self.gc.screen_state == sts.ScreenState.BATTLE: # WHEN SWITCHING TO BATTLE
            if self.bc_initiated == False:
                self.bc.init(self.gc)
                self.bc_initiated = True
            if self.bc.outcome != sts.BattleOutcome.UNDECIDED:
                self.bc.exit_battle(self.gc)
                self.bc_initiated = False

    
    def card_describe(self, card, upgraded=None):
        # Takes a Card, a CardId, or a plain id string.
        return describe_card(card, upgraded)


    def relic_describe(self, relic):
        # Takes a Relic, a RelicId, or a plain id string. Relics have no upgrade
        # dimension, so there is no second argument.
        return describe_relic(relic)


    def potion_describe(self, potion):
        # Takes a Potion enum or a plain id string; an empty slot describes itself
        # as '(empty slot)' rather than raising.
        return describe_potion(potion)


    def status_describe(self, status, amount=None, owner=None):
        # Takes a PlayerStatus/MonsterStatus or an id string. `amount` is the stack
        # count; `owner` only matters for a bare string ('WEAK' is the player's by
        # default, owner="MONSTER" for an enemy's).
        return describe_status(status, amount, owner)


    def view_statuses(self):
        """Every status effect currently in play, described — yours and each enemy's."""
        if self.gc.screen_state != sts.ScreenState.BATTLE or not self.bc_initiated:
            return "No combat in progress, so nothing has any status effects."

        blocks = []
        player = _active_statuses(self.bc.player, sts.PlayerStatus)
        blocks.append(status_glossary(player, header="You:") if player
                      else "You: no status effects.")

        for i, monster in enumerate(self.bc.monsters):
            if monster.is_dead_or_escaped:
                continue
            header = f"{_monster_name(self.bc, i)}:"
            active = _active_statuses(monster, sts.MonsterStatus)
            blocks.append(status_glossary(active, header=header) if active
                          else f"{header} no status effects.")

        return "\n".join(blocks)


    def view_deck(self):
        deck = self.gc.deck
        clean_deck = []
        for card in deck:
            card = str(card)
            card = card.replace("<slaythespire.Card ", "")
            card = card.replace(">", "")
            clean_deck.append(card)
        return clean_deck

    def view_relics(self):
        """Every relic you're carrying, described.

        `Relic` objects have no `__repr__`, so relic_text reads `.id` and pulls the name
        and effect text from `relic_data.json`.
        """
        relics = self.gc.relics
        if not relics:
            return "You have no relics."
        return relic_glossary(relics, header="Relics:")

    def view_potions(self):
        """Every potion in your belt, described, with the slot count.

        Reads `bc.potions` mid-combat: bc holds its own copy of the belt and only writes
        it back on `exit_battle`, so `gc.potions` goes stale during a fight.
        """
        in_battle = self.gc.screen_state == sts.ScreenState.BATTLE and self.bc_initiated
        potions = self.bc.potions if in_battle else self.gc.potions

        held = [p for p in potions if not potion_text.is_empty(p)]
        if not held:
            return f"Potions: none (0/{len(potions)} slots full)."
        return potion_glossary(held, header=f"Potions ({len(held)}/{len(potions)} slots full):")

    
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
# constants/Potions.h). potion_data.json's flag covers only the Ironclad pool, which
# misses Poison Potion.
TARGETED_POTIONS = {
    sts.Potion.FEAR_POTION,
    sts.Potion.FIRE_POTION,
    sts.Potion.POISON_POTION,
    sts.Potion.WEAK_POTION,
}


def _tail(enum_val) -> str | None:
    """ScreenState.MAP_SCREEN -> 'MAP_SCREEN'; None stays None."""
    return None if enum_val is None else str(enum_val).split(".")[-1]


# Short display names for action lines; the full effect text belongs in the
# glossaries the state encoder builds.
def _enum_name(enum_val) -> str:
    """Fallback for ids the game_data tables don't cover (non-Ironclad pools):
    RelicId.BLOOD_VIAL -> 'Blood Vial'."""
    return _tail(enum_val).replace("_", " ").title()


def _card_name(card, upgraded=None) -> str:
    """A Card -> 'Bash' / 'Bash+' (reward and shop cards can roll upgraded).

    Also takes a plain id string with `upgraded` spelled out, which is how
    env/observe.py names a card without re-reading its pybind properties.
    """
    data = card_text.get(card)
    name = data.name if data else _enum_name(getattr(card, "id", card))
    if upgraded is None:
        upgraded = getattr(card, "upgraded", False)
    return name + ("+" if upgraded else "")


def _relic_name(relic) -> str:
    data = relic_text.get(relic)
    return data.name if data else _enum_name(relic)


def _potion_name(potion) -> str:
    data = potion_text.get(potion)
    return data.name if data else _enum_name(potion)


@cache
def _scannable_statuses(enum_cls):
    """((status, stacks), ...) for one status enum, INVALID dropped.

    Precomputed because `_active_statuses` now runs on every snapshot, not just when
    `view_statuses()` is called by hand. Resolving each id's `stacks` flag through
    status_text on every pass was most of the loop's cost, and those flags never change.
    """
    out = []
    for name, status in enum_cls.__members__.items():
        if name == "INVALID":
            continue
        data = status_text.get(status)
        out.append((status, data is None or data.stacks))
    return tuple(out)


def _active_statuses(holder, enum_cls):
    """[(status, amount)] for everything currently on a Player or a Monster.

    The engine only answers one id at a time, so this walks the whole enum. `amount` is
    None for flag-only powers (Barricade, Corruption, ...), which raise instead of
    returning 1; `status_data.json` says which is which. The `or amount` catches Monster
    Strength, which lives in a field the status bit doesn't track.
    """
    active = []
    for status, stacks in _scannable_statuses(enum_cls):
        amount = None
        if stacks:
            try:
                amount = holder.get_status(status)
            except IndexError:      # flag-only after all — describe it without a count
                amount = None
        if holder.has_status(status) or amount:
            active.append((status, amount))
    return active


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
        # Engine quirk: every gold pile is enumerated with idx1=0, so two piles show
        # up as two identical lines and executing either takes pile 0.
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
    """'Jaw Worm (enemy 0)' — the index disambiguates same-name enemies (3 Cultists)."""
    monsters = bc.monsters
    if 0 <= idx < len(monsters):
        # Monster.name is the raw id string ('JAW_WORM'), not a display name.
        return f"{_enum_name(monsters[idx].name)} (enemy {idx})"
    return f"enemy {idx}"


def _pile_card(cards, idx) -> str:
    """Name the card an index points at, for any of the combat piles."""
    return _card_name(cards[idx]) if 0 <= idx < len(cards) else f"card {idx}"


def _card_select_pile(task, bc, info):
    """Which pile a card-select index points into, for a given task.

    The single source of truth for the mapping in isValidSingleCardSelectAction
    (src/sim/search/Action.cpp). Both the describer below and `env/observe.py` read it,
    so a newly implemented task only has to be classified in one place.
    """
    t = sts.CardSelectTask
    if task in (t.CODEX, t.DISCOVERY):
        return info.cards
    if task == t.EXHUME:
        return bc.cards.exhaust_pile
    if task in (t.HOLOGRAM, t.LIQUID_MEMORIES_POTION, t.MEDITATE, t.HEADBUTT):
        return bc.cards.discard_pile
    if task in (t.SEEK, t.SECRET_TECHNIQUE, t.SECRET_WEAPON):
        return bc.cards.draw_pile
    return bc.cards.hand        # everything left selects out of the hand


def _describe_card_select(a, bc):
    """CARD_SELECT input state — the *task* decides which pile the index points into,
    so dispatch on the task and name the card. The piles come from
    isValidSingleCardSelectAction in src/sim/search/Action.cpp.
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
    pile = _card_select_pile(task, bc, info)

    if task in (t.CODEX, t.DISCOVERY):
        return f"add {_pile_card(pile, idx)} to your hand"

    if task == t.EXHUME:
        return f"return {_pile_card(pile, idx)} from the exhaust pile"

    if task in (t.HOLOGRAM, t.LIQUID_MEMORIES_POTION, t.MEDITATE):
        return f"return {_pile_card(pile, idx)} from the discard pile"

    if task == t.HEADBUTT:
        card = _pile_card(pile, idx)
        return f"put {card} from the discard pile on top of the draw pile"

    if task in (t.SEEK, t.SECRET_TECHNIQUE, t.SECRET_WEAPON):
        return f"take {_pile_card(pile, idx)} from the draw pile"

    # Everything left selects out of the hand.
    card = _pile_card(pile, idx)

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

    Replaces the engine's `a.describe(bc)` with out-of-combat phrasing and the card
    named in every card-select task.
    """
    at = a.action_type

    if at == sts.ActionType.END_TURN:
        return "end turn"

    if at == sts.ActionType.CARD:
        hand = bc.cards.hand
        i = a.source_idx
        # Untargeted cards are enumerated with target_idx 0 too, so the card itself
        # is what says whether it aims.
        if 0 <= i < len(hand) and hand[i].requires_target:
            return f"play {_pile_card(hand, i)} on {_monster_name(bc, a.target_idx)}"
        return f"play {_pile_card(hand, i)}"

    if at == sts.ActionType.POTION:
        potions = bc.potions
        i = a.source_idx
        if not 0 <= i < len(potions):
            return f"use the potion in slot {i}"
        name = _potion_name(potions[i])
        # A discard is target -1, which reads back as 8191 (13 bits). Untargetable
        # and always-discard potions (Fairy in a Bottle) land here too.
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


