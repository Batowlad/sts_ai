"""Typed value objects for game state and actions.

Deliberately dependency-free - no `slaythespire` import, no `game_interface` import.
That is what lets `env/observe.py` import this module *and* `game_interface` without a
cycle. Builders live in `env/observe.py`, rendering in `env/render.py`.

Every container is a `tuple`, never a `list`. `frozen=True` does not deep-freeze, and a
mutable list inside a snapshot is exactly the aliasing bug these types exist to prevent:
`bc.player`, `bc.monsters` and `bc.cards` are live views into C++ memory that mutate
under you the moment you `execute()` the next action.

For a rollout log, `dataclasses.asdict(obs)` gives a plain dict that `json.dumps` takes
as-is (`ActionKind` is a `str` enum, so it serializes to its value).

Named `game_types` rather than `types` on purpose: `env/` goes on `sys.path[0]`, so a
module called `types.py` would shadow the stdlib one for every flat import in the
process.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionKind(str, Enum):
    """What an action *does*, independent of which screen enumerated it."""

    # combat
    PLAY_CARD = "play_card"
    END_TURN = "end_turn"
    SELECT_CARD = "select_card"
    SELECT_CARDS = "select_cards"
    # potions (any screen)
    USE_POTION = "use_potion"
    DISCARD_POTION = "discard_potion"
    # out of combat
    MAP_MOVE = "map_move"
    EVENT_OPTION = "event_option"
    REST_OPTION = "rest_option"
    TREASURE_OPTION = "treasure_option"
    BOSS_RELIC = "boss_relic"
    TAKE_REWARD = "take_reward"
    SHOP_BUY = "shop_buy"
    SHOP_REMOVE = "shop_remove"
    DECK_SELECT = "deck_select"
    SKIP = "skip"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ActionOption:
    """One legal choice, carrying enough identity to survive a round-trip to disk.

    `index` is what `GameInterface.step()` takes, but it only means something for the
    step that produced it - the engine re-enumerates the legal list after every action.
    `key` is what to log, diff and train on. `bits` is the engine's own packing of the
    decision (`Action.bits` / `GameAction.bits`), which is what `step()` replays.

    `screen` travels with the option because a `GameAction`'s bits are relative to the
    screen that enumerated them: `idx1 = 0` is the first event option on EVENT_SCREEN
    and "move to map node x=0" on MAP_SCREEN. `step()` refuses an option from another
    screen rather than execute whatever its bits happen to decode as there.
    """

    index: int
    kind: ActionKind
    label: str
    screen: str | None = None
    bits: int | None = None
    card_id: str | None = None
    relic_id: str | None = None
    potion_id: str | None = None
    target_idx: int | None = None       # the monster aimed at, when the action aims
    idx1: int | None = None
    idx2: int | None = None
    selected_idxs: tuple[int, ...] = ()

    @property
    def key(self) -> str:
        """Position-independent identity: 'play_card:BASH->0', 'map_move:3'.

        Two options from different steps share a key iff they mean the same decision,
        which is what makes a logged dataset greppable and a test assertable.
        """
        key = self.kind.value
        subject = self.card_id or self.relic_id or self.potion_id
        if subject:
            key += f":{subject}"
        elif self.idx1 is not None:
            key += f":{self.idx1}"
        if self.target_idx is not None:
            key += f"->{self.target_idx}"
        if self.selected_idxs:
            key += "+" + "+".join(map(str, self.selected_idxs))
        return key


@dataclass(frozen=True, slots=True)
class StatusView:
    id: str                       # 'VULNERABLE'
    amount: int | None = None     # None for flag-only powers (Barricade, Corruption)
    owner: str = "PLAYER"         # 'PLAYER' | 'MONSTER' - the same id lives in both enums


@dataclass(frozen=True, slots=True)
class CardView:
    id: str                           # 'BASH' - engine id, stable across runs
    name: str                         # 'Bash+' - display name, '+' when upgraded
    upgraded: bool = False
    # Only read for cards the policy can act on (the hand and card-select offers);
    # observe._card_view says why the piles skip them.
    cost: int | None = None           # cost this turn
    card_type: str | None = None      # 'ATTACK'
    requires_target: bool = False
    exhausts: bool = False
    ethereal: bool = False


@dataclass(frozen=True, slots=True)
class RelicView:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class PotionView:
    id: str
    name: str
    slot: int = -1
    is_empty: bool = False


@dataclass(frozen=True, slots=True)
class PlayerView:
    cur_hp: int
    max_hp: int
    block: int
    energy: int
    strength: int = 0
    dexterity: int = 0
    stance: str | None = None
    statuses: tuple[StatusView, ...] = ()


@dataclass(frozen=True, slots=True)
class MonsterView:
    idx: int
    id: str                             # 'CULTIST'
    name: str                           # 'Cultist (enemy 0)' - the idx disambiguates
    cur_hp: int
    max_hp: int
    block: int = 0
    intent: str | None = None           # current move id, the in-game "intent"
    is_attacking: bool = False
    attack_damage: int | None = None    # base damage *per hit*, before modifiers
    attack_count: int | None = None
    incoming_damage: int | None = None  # per hit, after strength/weak/vulnerable
    is_dead_or_escaped: bool = False
    statuses: tuple[StatusView, ...] = ()


@dataclass(frozen=True, slots=True)
class CombatView:
    """A detached copy of the battle state.

    `draw_pile` is kept in engine order because a snapshot should capture everything,
    but a player cannot see that order. What the policy may look at is the renderer's
    call, not this type's - see `render.py`. The potion belt lives on `Observation`.
    """

    turn: int
    encounter: str
    outcome: str
    input_state: str
    player: PlayerView
    monsters: tuple[MonsterView, ...] = ()
    hand: tuple[CardView, ...] = ()
    draw_pile: tuple[CardView, ...] = ()
    discard_pile: tuple[CardView, ...] = ()
    exhaust_pile: tuple[CardView, ...] = ()
    card_select_task: str | None = None
    card_select_pick_count: int | None = None
    card_select_can_pick_zero: bool = False
    card_select_cards: tuple[CardView, ...] = ()


@dataclass(frozen=True, slots=True)
class RoomRange:
    """How many rooms of one type a route can pass through: the fewest and the most
    over every path from a node to the top of the act, the node itself included."""

    room: str               # 'ELITE', 'REST', ...
    min: int
    max: int


@dataclass(frozen=True, slots=True)
class MapChoice:
    """One node you can move to next, and what the routes through it hold."""

    x: int
    y: int
    room: str               # this node's room type
    ahead: tuple[RoomRange, ...] = ()


@dataclass(frozen=True, slots=True)
class MapView:
    x: int
    y: int                  # -1 until the first node is chosen
    ascii_map: str = ""
    choices: tuple[MapChoice, ...] = ()     # empty on the top row: next is the boss


@dataclass(frozen=True, slots=True)
class RewardsView:
    gold: tuple[int, ...] = ()
    card_bundles: tuple[tuple[CardView, ...], ...] = ()
    relics: tuple[RelicView, ...] = ()
    potions: tuple[PotionView, ...] = ()
    emerald_key: bool = False
    sapphire_key: bool = False


@dataclass(frozen=True, slots=True)
class ShopEntry:
    slot: int
    id: str
    name: str
    price: int
    upgraded: bool = False  # shop cards can roll upgraded


@dataclass(frozen=True, slots=True)
class ShopView:
    cards: tuple[ShopEntry, ...] = ()
    relics: tuple[ShopEntry, ...] = ()
    potions: tuple[ShopEntry, ...] = ()
    remove_cost: int = 0


@dataclass(frozen=True, slots=True)
class EventView:
    name: str
    event_data: int = 0     # phase counter for multi-phase events (Cursed Tome, ...)


@dataclass(frozen=True, slots=True)
class Observation:
    """One decision point, fully detached from the engine.

    The common fields are filled on every screen, so a screen with no block of its own
    still yields a thin-but-valid observation - where the old string-returning
    `encode_state` returned None (TREASURE_ROOM, for one). At most one of the screen
    blocks below is set, matching `screen`.
    """

    screen: str
    floor: int
    act: int
    cur_hp: int
    max_hp: int
    gold: int
    outcome: str
    potion_count: int = 0
    potion_capacity: int = 0
    deck: tuple[CardView, ...] = ()
    relics: tuple[RelicView, ...] = ()
    potions: tuple[PotionView, ...] = ()    # bc's belt mid-fight, gc's otherwise
    keys: tuple[str, ...] = ()
    combat: CombatView | None = None
    map_view: MapView | None = None
    rewards: RewardsView | None = None
    shop: ShopView | None = None
    event: EventView | None = None
    boss_relics: tuple[RelicView, ...] = ()     # BOSS_RELIC_REWARDS only
    select_cards: tuple[CardView, ...] = ()     # CARD_SELECT only (Neow, events, Smith...)
    select_verb: str | None = None              # what picking one does: 'upgrade', 'remove'...
