# `slaythespire` Python module — API reference

The `slaythespire` pybind11 module is the Python surface of the `sts_lightspeed`
C++ engine. **Only the symbols listed here are exposed to Python** — the C++
`GameContext`/`BattleContext` have hundreds of methods, but the binding
(`sts_lightspeed/bindings/slaythespire.cpp`) only surfaces the subset below.

Import shim (already handled by `env/game_interface.py`):

```python
from env.game_interface import sts          # -> the slaythespire module
gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed=42, ascension=0)
```

`__version__` is defined on the module (`"dev"` unless built with `VERSION_INFO`).

> Source of truth: `sts_lightspeed/bindings/slaythespire.cpp` (bindings) and
> `sts_lightspeed/bindings/bindings-util.cpp` (the `sts::py::*` helper impls).

---

## Module-level functions

| Function | Signature | Notes |
|---|---|---|
| `play()` | `play() -> None` | Launches the interactive console simulator, reading/writing `std::cin`/`std::cout`. **Blocking & interactive** — not useful from a normal Python script. |
| `get_seed_str(seed)` | `get_seed_str(int) -> str` | Convert an integral seed → the in-game UI seed string (e.g. `"ABC123"`). Wraps `SeedHelper::getString`. |
| `get_seed_long(seed)` | `get_seed_long(str) -> int` | Convert a UI seed string → its integral (`uint64`) value. Wraps `SeedHelper::getLong`. |
| `event_game_name(e)` | `event_game_name(Event) -> str` | In-game display name of an `Event`, e.g. `"Hypnotizing Colored Mushrooms"`. |
| `getNNInterface()` | `getNNInterface() -> NNInterface` | Returns the singleton `NNInterface` used to encode a `GameContext` into an observation vector. |
| `get_legal_actions(bc)` | `get_legal_actions(bc: BattleContext) -> list[Action]` | All combat actions valid in `bc`'s current input state. Same as `bc.legal_actions()`. |

---

## Classes

### `GameContext`
The top-level run state (map traversal / out-of-combat). Combat can be played
two ways: automatically inside `Agent.playout`, or stepped action-by-action
from Python with `BattleContext` + `Action` (see the **Combat** section).
Out-of-combat decisions are stepped with `GameAction`.

**Constructor**
```python
GameContext(character: CharacterClass, seed: int, ascension: int)
```

**Methods**

| Method | Signature | Notes |
|---|---|---|
| `pick_reward_card` | `(card: Card) -> None` | Obtain `card` from the current card-reward list. Requires `screen_state == REWARDS` with rewards present, else prints to stderr and no-ops. |
| `skip_reward_cards` | `() -> None` | Skip the current card reward. With **Singing Bowl** relic, raises `max_hp` by 2. Same state precondition as above. |
| `get_card_reward` | `() -> list[Card]` | The current card-reward choices. Returns `[]` (and warns) if not on a rewards screen. |
| `obtain_card` | `(card: Card) -> None` | Add a card to the deck (`deck.obtain`). |
| `remove_card` | `(idx: int) -> None` | Remove the card at deck index `idx`. Out-of-range index warns to stderr and no-ops. |
| `__repr__` | `() -> str` | Human-readable dump of the context. |

**Read-only properties**

| Property | Type | Notes |
|---|---|---|
| `encounter` | `MonsterEncounter` | Current encounter (`info.encounter`). |
| `deck` | `list[Card]` | **Copy** of the deck's cards. Mutating the list won't change the deck — use `obtain_card`/`remove_card`. |
| `relics` | `list[Relic]` | **Copy** of the relic list. |
| `potions` | `list[Potion]` | **Copy** of the potion slots (length = `potion_capacity`; empty slots are `Potion.EMPTY_POTION_SLOT`). |
| `cur_event_name` | `str` | In-game display name of `cur_event`, e.g. `"Big Fish"`. |
| `event_data` | `int` | Phase/progress counter for multi-phase events (Cursed Tome pages, Scrap Ooze attempts, Colosseum round). |
| `event_info` | `dict` | Raw per-event state (`hp_amount0..2`, `phase`, `gold_loss`, `gold`, `potion_idx`, `card_idx`, `relic_idx0/1`, `upgrade_one`, `clean_up_is_remove_card`, `skill/power/attack_card_deck_idx`, `event_data`). **Only the fields the current event uses are meaningful** — the rest are uninitialized garbage. |
| `neow_rewards` | `list[NeowOption]` | The four Neow options; only meaningful while the `NEOW` event screen is active. |
| `rewards_container` | `dict` | Pending rewards; only meaningful while `screen_state == REWARDS`. Keys: `gold` (`list[int]`), `cards` (`list[list[Card]]` — one inner list per reward bundle), `relics` (`list[RelicId]`), `potions` (`list[Potion]`), `emerald_key` / `sapphire_key` (`bool`). List positions line up with `GameAction.idx1` (and `idx2` for cards). |
| `shop` | `dict` | Shop stock; only meaningful while `screen_state == SHOP_ROOM`. Keys: `cards` (7), `relics` (3), `potions` (3), the matching `card_prices` / `relic_prices` / `potion_prices` (**`-1` = empty slot**), and `remove_cost`. List positions line up with `GameAction.idx1`. |
| `boss_relics` | `list[RelicId]` | The three boss relics on offer; only meaningful while `screen_state == BOSS_RELIC_REWARDS` (uninitialized garbage before the first boss). |

**Read/write fields**

| Field | Type | Default / notes |
|---|---|---|
| `outcome` | `GameOutcome` | `UNDECIDED` until win/loss. |
| `cur_event` | `Event` | Current event (meaningful on `EVENT_SCREEN`). |
| `act` | `int` | 1-based act. |
| `ascension` | `int` | |
| `floor_num` | `int` | |
| `potion_count` | `int` | |
| `potion_capacity` | `int` | 3 by default, +2 with Potion Belt. |
| `screen_state` | `ScreenState` | Current screen (drives which actions are valid). |
| `seed` | `int` | `uint64`. |
| `cur_map_node_x` | `int` | `-1` until on the map. |
| `cur_map_node_y` | `int` | `-1` until on the map. |
| `cur_room` | `Room` | |
| `boss` | `MonsterEncounter` | Act boss. |
| `cur_hp` | `int` | |
| `max_hp` | `int` | |
| `gold` | `int` | |
| `blue_key` | `bool` | Sapphire key. |
| `green_key` | `bool` | Emerald key. |
| `red_key` | `bool` | Ruby key. |
| `card_rarity_factor` | `int` | Affects reward rarity rolls (default 5). |
| `potion_chance` | `int` | |
| `monster_chance` | `float` | |
| `shop_chance` | `float` | |
| `treasure_chance` | `float` | |
| `shop_remove_count` | `int` | |
| `speedrun_pace` | `bool` | |
| `note_for_yourself_card` | `Card` | Card for the "Note For Yourself" mechanic. |

> Not exposed to Python: RNG streams, relic/event/monster pools, the `map`
> object, and the many `chooseX`/`generateX` methods on the C++ `GameContext`
> (drive those with `GameAction` instead). Add bindings in `slaythespire.cpp`
> if you need them.

---

### `Card`

**Constructor**
```python
Card(id: CardId)            # un-upgraded
```

**Methods / fields**

| Member | Signature / Type | Notes |
|---|---|---|
| `upgrade()` | `() -> None` | Upgrade in place. |
| `misc` | `int` (read/write) | Simulator-internal value (e.g. Ritual Dagger damage, Genetic Algorithm block, Searing Blow upgrade count). |
| `__repr__()` | `() -> str` | e.g. `<slaythespire.Card Strike+>`. |

**Read-only properties**

| Property | Type | Notes |
|---|---|---|
| `id` | `CardId` | |
| `upgraded` | `bool` | |
| `upgrade_count` | `int` | Number of upgrades (matters for Searing Blow). |
| `innate` | `bool` | |
| `transformable` | `bool` | Can be transformed. |
| `upgradable` | `bool` | Can be upgraded. |
| `is_strikeCard` | `bool` | Any "Strike" card (Perfected Strike synergy). |
| `is_starter_strike_or_defend` | `bool` | |
| `rarity` | `CardRarity` | |
| `type` | `CardType` | |

---

### `Relic`  (C++ `RelicInstance`)

| Field | Type | Notes |
|---|---|---|
| `id` | `RelicId` | |
| `data` | `int` | Per-relic counter/state (e.g. charges, stacks). |

---

### `SpireMap`  (C++ `Map`)

**Constructor**
```python
SpireMap(seed: int, ascension: int, act: int, assign_burning_elite: bool)
```

**Methods**

| Method | Signature | Notes |
|---|---|---|
| `get_room_type` | `(x: int, y: int) -> Room` | Returns `Room.INVALID` for out-of-range (`x∉[0,6]` or `y∉[0,14]`). |
| `has_edge` | `(x: int, y: int, x2: int) -> bool` | Is there an edge from node `(x,y)` to column `x2` in the next row? Special case: `x == -1` tests whether column `x2` of row 0 is a valid start node. |
| `get_nn_rep` | `() -> list[int]` | Flattened neural-net map encoding: 7 start bits + 21 bits/row of edge directions (13 rows) + 6 room-type one-hot bits per node for the variable rows. |
| `__repr__` | `() -> str` | ASCII map (`toString(true)`). |

Grid is 7 columns (`x` 0–6) × 15 rows (`y` 0–14).

---

### `NNInterface`  (singleton — get via `getNNInterface()`)

| Member | Signature | Notes |
|---|---|---|
| `getObservation` | `(gc: GameContext) -> list[int]` | Encodes a run state into a length-**412** integer vector: `[cur_hp, max_hp, gold, floor_num]`, 10 boss one-hot slots, 220 card slots (110 cards × {base, upgraded}, capped at `cardCountMax=7` each), 178 relic slots. |
| `getObservationMaximums` | `() -> list[int]` | Element-wise maximums for the observation space (for normalization). HP capped at 200, gold at 1800, floor at 60. |
| `observation_space_size` | `int` property (= `412`) | Read-only constant. |

---

### `Agent`  (C++ `search::ScumSearchAgent2`)

Monte-Carlo-tree-search agent that plays a `GameContext` automatically.

**Constructor**
```python
Agent()
```

| Member | Type / Signature | Default | Notes |
|---|---|---|---|
| `simulation_count_base` | `int` (read/write) | `50000` | MCTS simulations per turn. |
| `boss_simulation_multiplier` | `float` (read/write) | `3` | Extra multiplier for boss fights. |
| `pause_on_card_reward` | `bool` (read/write) | `False` | Pause (cede control to caller) at card-reward choices. |
| `print_logs` | `bool` (read/write) | `False` | Print state info while acting. |
| `playout(gc)` | `(gc: GameContext) -> None` | — | Play the run (or until a pause condition) in place. |

---

## Combat — stepping battles from Python

Combat lives in a separate `BattleContext`, stepped with `Action`s — the same
discrete action MDP the MCTS agent uses internally. The canonical loop:

```python
from env.game_interface import sts

# ... advance gc (via GameAction) until gc.screen_state == sts.ScreenState.BATTLE ...
bc = sts.BattleContext()
bc.init(gc)

while bc.outcome == sts.BattleOutcome.UNDECIDED:
    actions = bc.legal_actions()      # list[Action], all valid
    a = my_policy(bc, actions)
    a.execute(bc)                     # applies + runs engine to the next decision point

bc.exit_battle(gc)                    # hp/gold/potions/relics/cards written back to gc
# victory -> the run continues (usually REWARDS screen); defeat -> gc.outcome == PLAYER_LOSS
```

`bc.player`, `bc.monsters`, `bc.cards` and `bc.card_select_info` are **live
views** into the battle — they reflect every executed action. The card piles
(`hand`, `draw_pile`, …), `potions` and `card_select_info.cards` are returned
as **copies**.

For the text the policy actually reads, `env/game_interface.py::describe_battle(a, bc)`
turns an action into a line like `"play Bash on Jaw Worm (enemy 0)"` /
`"upgrade Defend"` — the combat counterpart of `describe(a, gc)`.
`GameInterface.legal_actions()` returns those descriptions on the `BATTLE`
screen, in the order `step()` indexes into.

### `BattleContext`

**Constructors**
```python
BattleContext()            # empty; call init() next
BattleContext(other)       # full copy — cheap; for Python-side rollouts/MCTS
```
`copy.copy` / `copy.deepcopy` also work.

| Method | Signature | Notes |
|---|---|---|
| `init` | `(gc: GameContext) -> None` | Build combat state from `gc` (encounter, deck, relics, hp, potions, rng). Raises `ValueError` unless `gc.screen_state == BATTLE`. |
| `init` | `(gc: GameContext, encounter: MonsterEncounter) -> None` | Fight an explicit encounter; `gc` supplies everything else. No screen-state check. |
| `exit_battle` | `(gc: GameContext) -> None` | Write results back to `gc`. Raises `ValueError` while `outcome == UNDECIDED`. On victory the run continues; on defeat sets `gc.outcome = PLAYER_LOSS`. |
| `legal_actions` | `() -> list[Action]` | All valid actions for the current `input_state`. |
| `__repr__` | `() -> str` | Full battle-state dump. |

**Read-only properties**

| Property | Type | Notes |
|---|---|---|
| `outcome` | `BattleOutcome` | `UNDECIDED` / `PLAYER_VICTORY` / `PLAYER_LOSS`. |
| `input_state` | `InputState` | `PLAYER_NORMAL` or `CARD_SELECT` at decision points. |
| `turn` | `int` | |
| `is_battle_over` | `bool` | |
| `encounter` | `MonsterEncounter` | |
| `ascension` / `seed` / `floor_num` | `int` | |
| `player` | `Player` | **Live view.** |
| `monsters` | `MonsterGroup` | **Live view.** |
| `cards` | `CardManager` | **Live view.** |
| `card_select_info` | `CardSelectInfo` | **Live view.** What a `CARD_SELECT` state is asking. |
| `potion_count` / `potion_capacity` | `int` | |
| `potions` | `list[Potion]` | **Copy**, length = `potion_capacity`. |

**`legal_actions()` semantics** (vs. the MCTS searcher's internal enumerator):

- Identical cards in hand are **not** deduplicated, so action indices are
  stable (the searcher prunes duplicates as an MCTS optimization).
- For `EXHAUST_MANY` / `GAMBLE` selects only the "pick nothing" action is
  enumerated (engine behavior). Richer picks can be built manually with
  `Action(ActionType.MULTI_CARD_SELECT, mask)` where bit *i* of `mask`
  selects hand index *i* — `Action.is_valid` accepts any legal subset.
- For card-select tasks of not-fully-implemented characters (`HOLOGRAM`,
  `MEDITATE`, `NIGHTMARE`, `RECYCLE`, `SETUP`, `SEEK`) it returns `[]` even
  though `outcome == UNDECIDED`. Treat an empty list as an error state —
  Ironclad play never hits it.

### `Action`  (C++ `search::Action`)

A 32-bit packed combat action.

**Constructors**
```python
Action(action_type)                 # END_TURN
Action(action_type, idx1)           # untargeted CARD/POTION, card selects, multi-select mask
Action(action_type, idx1, idx2)     # targeted CARD/POTION (idx2 = monster idx, or -1 to discard a potion)
Action.from_bits(bits)              # reconstruct from .bits
```

| Member | Type / Signature | Notes |
|---|---|---|
| `action_type` | `ActionType` | |
| `source_idx` | `int` | Hand idx (CARD) / potion slot (POTION). |
| `target_idx` | `int` | Monster idx; for POTION a value **> 5 means discard**. |
| `select_idx` | `int` | For `SINGLE_CARD_SELECT`. |
| `selected_idxs` | `list[int]` | For `MULTI_CARD_SELECT`. |
| `bits` | `int` | Raw stable encoding — good for replay logs. |
| `is_valid(bc)` | `-> bool` | Full legality check against the battle state. |
| `execute(bc)` | `-> None` | Apply + run the engine to the next decision point. **Raises `ValueError` if not valid.** |
| `describe(bc)` | `-> str` | Human-readable, e.g. `{ use card (0) Strike -> (0) Jaw Worm }`. Card selects only print the task name (the C++ helper doesn't know which pile the index is in) — use `env/game_interface.py::describe_battle(a, bc)` for those. |

Hashable, comparable with `==` (by bits); `repr()` needs no battle context.

### `GameAction`  (C++ `search::GameAction`) — out-of-combat decisions

**Constructors:** `GameAction(idx1, idx2=0)`,
`GameAction(rewards_type: RewardsActionType, idx1=0, idx2=0)`,
`GameAction.from_bits(bits)`.

| Member | Type / Signature | Notes |
|---|---|---|
| `GameAction.get_all_actions_in_state(gc)` | `static -> list[GameAction]` | All valid actions for the current screen. **Empty** on the `BATTLE` screen (hand off to `BattleContext`), after the game ends, and for the unimplemented `MATCH_AND_KEEP` event. |
| `idx1` / `idx2` / `idx3` | `int` | Meaning depends on the screen — see the decoding guide below. `idx3` is never set in practice. |
| `rewards_action_type` | `RewardsActionType` | Only meaningful on the `REWARDS` screen. |
| `is_potion_action` / `is_potion_discard` | `bool` | Potions can be drunk/discarded on most screens. |
| `is_valid(gc)` | `-> bool` | |
| `execute(gc)` | `-> None` | **Raises `ValueError` if not valid.** |
| `describe(gc)` | `-> str` | **Stub** — the C++ `printDesc` prints nothing, so this always returns `""`. Use `env/game_interface.py::describe(a, gc)` instead (event text comes from `env/event_options.py`). |

#### Reading `GameAction` indices (`idx1` / `idx2` / `idx3`)

A `GameAction` is a packed 32-bit integer; `idx1` / `idx2` / `idx3` are just
slices of it, and what they *mean* depends on `gc.screen_state`:

```
bits  0–7   idx1
bits  8–15  idx2
bits 16–23  idx3   (never written by any constructor — always 0 in practice)
bits 27–29  rewards_action_type  (only meaningful on REWARDS / SHOP screens)
bit  30     is_potion_discard
bit  31     is_potion_action
```

Check `is_potion_action` **first** — potion actions can occur on any screen.
If true: `idx1` = potion slot, and `is_potion_discard` distinguishes discard
from drink. Otherwise, by `gc.screen_state`:

| Screen | Meaning |
|---|---|
| `EVENT_SCREEN` | `idx1` = event option number (same order as the in-game buttons). Option numbers are **fixed slots per event** (`GameAction::getValidEventSelectBits`): unavailable options are absent from the legal list but the rest keep their numbers. Decode which event via `gc.cur_event` and get option text with `env/event_options.py::describe_event_option(gc, idx1)` (a port of `ConsoleSimulator::printEventActions`, faithful to what the sim actually executes). Neow options are dynamic — read `gc.neow_rewards`. |
| `MAP_SCREEN` | `idx1` = x-coordinate of the map node to move to (0–6) |
| `REST_ROOM` | `idx1`: 0=rest, 1=smith/upgrade, 2=take ruby key, 3=Girya lift, 4=Peace Pipe toke, 5=Shovel dig, 6=skip |
| `TREASURE_ROOM` | `idx1`: 0=open chest, 1=skip |
| `BOSS_RELIC_REWARDS` | `idx1` = which boss relic (0–2, index into `gc.boss_relics`), 3=skip |
| `CARD_SELECT` | `idx1` = index into `gc.info.toSelectCards` |
| `REWARDS` | dispatch on `rewards_action_type`, see below |
| `SHOP_ROOM` | dispatch on `rewards_action_type`, see below |

On **`REWARDS`**, `rewards_action_type` picks the reward kind, and the indices
address `gc.rewards_container`:

* `CARD` — `idx1` = which card-reward bundle, `idx2` = which card inside it,
  i.e. `gc.rewards_container["cards"][idx1][idx2]`.
  (`idx2 == 5` means Singing Bowl: +2 max HP instead of a card. It is *valid*
  but **not enumerated** by `get_all_actions_in_state` — build it by hand.)
* `GOLD` / `POTION` / `RELIC` — `idx1` = index into
  `gc.rewards_container["gold"] / ["potions"] / ["relics"]`
* `KEY` — indices unused; takes the sapphire key if
  `rewards_container["sapphire_key"]`, else the emerald one. Taking the
  sapphire key removes the **last** relic reward, and symmetrically taking the
  last relic clears the sapphire key — that's the chest key-or-relic choice.
* `SKIP` — indices unused; leaves the rewards screen

On **`SHOP_ROOM`**, indices address `gc.shop`:

* `CARD` — `idx1` = shop card slot (0–6): `gc.shop["cards"][idx1]`,
  price `gc.shop["card_prices"][idx1]`
* `RELIC` / `POTION` — `idx1` = slot (0–2), same layout
* `CARD_REMOVE` — buy a card removal for `gc.shop["remove_cost"]`
* `SKIP` — leave the shop

Use `env/game_interface.py::describe(a, gc)` — it decodes every screen into a
human-readable line (`"take relic: Bronze Scales (forfeits the sapphire key)"`,
`"buy card: Anger (52 gold)"`):

```python
from env.game_interface import sts, describe

for a in sts.GameAction.get_all_actions_in_state(gc):
    print(describe(a, gc))
```

Gotchas:

* `GameAction.describe(gc)` always returns `""` (C++ stub, see table above) —
  use `env/game_interface.py::describe(a, gc)`. The `repr()` at least shows the
  raw idx values.
* On `REWARDS`, `getAllRewardActions` enumerates every gold pile as
  `GOLD idx1=0`, so a second pile appears as a **duplicate** action (and taking
  either takes pile 0). Two identical "take N gold" lines are that quirk, not a
  decoding bug.
* `idx3` can be ignored: it is read out of bits 16–23, but no constructor ever
  writes there.
* This is all separate from the in-combat `Action` class (fields
  `source_idx` / `target_idx` / `select_idx`, used with `BattleContext`).

#### Taking actions on the event screen

On an event screen an action is a `GameAction` whose `idx1` is a **fixed option
slot** for that event. List the legal actions, optionally describe them, then
execute one:

```python
from env.game_interface import sts
from event_options import describe_event_option

assert gc.screen_state == sts.ScreenState.EVENT_SCREEN

# 1. Legal actions for the current event/phase
actions = sts.GameAction.get_all_actions_in_state(gc)   # list[GameAction]

# 2. (optional) human-readable text for each
for a in actions:
    print(a.idx1, describe_event_option(gc, a.idx1))

# 3. Apply one — runs gc.chooseEventOption(idx1) under the hood
actions[0].execute(gc)
```

You can also build the action directly; the slot number is all that matters:

```python
sts.GameAction(idx1=2).execute(gc)   # choose option slot 2
```

`execute` re-validates first and raises `ValueError` if the slot isn't legal for
the current state. Use `a.is_valid(gc)` to check without throwing.

Things specific to the event screen:

* **Slots are fixed, not compacted.** For `BIG_FISH`, slot 0 = Banana, 1 = Donut,
  2 = Box — always. Unavailable options (not enough gold, no upgradeable card,
  etc.) are simply absent from `get_all_actions_in_state`, but the remaining
  options keep their original numbers, so always drive off `idx1`, never list
  position. The slot→meaning map per event is in `env/event_options.py`; the
  bitmask deciding which slots appear is `GameAction::getValidEventSelectBits`.
* **Multi-phase events loop on the same screen.** `CURSED_TOME`, `COLOSSEUM`,
  `DEAD_ADVENTURER`, and `SCRAP_OOZE` advance `gc.event_data` and stay on
  `EVENT_SCREEN` with a different set of valid slots. After each `execute`,
  re-check `screen_state` and re-call `get_all_actions_in_state`.
* **Some options hand off to another screen** — card removal/upgrade/transform
  moves to `CARD_SELECT`, fights (`COLOSSEUM`, `MASKED_BANDITS`, `MINDBLOOM`…)
  move to `BATTLE`, others to `REWARDS` or `MAP_SCREEN`. The post-event state is
  whatever `screen_state` reports next; don't assume it returns to the map.
* **`MATCH_AND_KEEP` is unsupported** — `get_all_actions_in_state` returns an
  empty list for it.
* **Potions are separate** (`a.is_potion_action`), and drinking/discarding is
  disabled during the `WE_MEET_AGAIN` event.

### `Player` — live combat view (read-only)

Fields: `character_class`, `cur_hp`, `max_hp`, `gold`, `block`, `energy`,
`energy_per_turn`, `card_draw_per_turn`, `stance`, `orb_slots`, `artifact`,
`dexterity`, `focus`, `strength`, `cards_played_this_turn`,
`attacks_played_this_turn`, `skills_played_this_turn`,
`cards_discarded_this_turn`, `combust_hp_loss`, and the relic counters
`happy_flower_counter`, `incense_burner_counter`, `ink_bottle_counter`,
`inserter_counter`, `nunchaku_counter`, `pen_nib_counter`, `sundial_counter`.

| Method | Signature | Notes |
|---|---|---|
| `has_status` | `(s: PlayerStatus) -> bool` | Works for every status incl. STRENGTH/DEXTERITY/FOCUS/ARTIFACT. |
| `get_status` | `(s: PlayerStatus) -> int` | Stack count / value; 0 when absent. |
| `has_relic` | `(r: RelicId) -> bool` | In-combat relic bits. |

### `Monster` — live combat view (read-only)

Fields: `idx`, `id` (`MonsterId`), `cur_hp`, `max_hp`, `block`, `strength`,
`misc_info` (monster-specific state, e.g. hexaghost orb count / champ phase).
Properties: `name`, `move_id` (`MonsterMoveId` — the current move, i.e. the
intent), `last_move_id`, `is_alive`, `is_targetable`, `is_dying`,
`is_escaping`, `is_dead_or_escaped`, `is_half_dead`, `does_escape_next`,
`is_attacking`.

| Method | Signature | Notes |
|---|---|---|
| `has_status` / `get_status` | `(s: MonsterStatus) -> bool / int` | |
| `get_move_base_damage` | `(bc) -> DamageInfo` | Base damage & hit count of the current move. |
| `calculate_damage_to_player` | `(bc, base_damage: int) -> int` | After strength/weak/vulnerable modifiers. |

### `MonsterGroup` — live combat view (read-only)

`monster_count`, `monsters_alive`, `targetable_count`,
`first_targetable_idx`, `are_monsters_basically_dead`. Supports `len(g)` and
`g[i]` (live `Monster` views), hence `for m in bc.monsters: ...`.

### `CardManager` — live combat view (read-only)

`cards_in_hand`; `hand`, `draw_pile`, `discard_pile`, `exhaust_pile` return
**copies** as `list[CardInstance]`.

### `CardInstance`

The in-combat card representation (distinct from the deck-level `Card`).
Constructor: `CardInstance(id: CardId, upgraded=False)`.

Fields/properties: `id`, `type`, `name`, `unique_id`, `special_data`
(per-card combat state, e.g. Ritual Dagger damage), `cost`, `cost_for_turn`,
`free_to_play_once`, `retain`, `upgraded`, `upgrade_count`, `upgradable`,
`is_ethereal`, `is_strike_card`, `does_exhaust`, `has_self_retain`,
`requires_target`, `is_x_cost`.

Methods: `is_free_to_play(bc)`, `can_use(bc, target, in_autoplay=False)`,
`can_use_on_any_target(bc)`.

### `CardSelectInfo`

Describes what a `CARD_SELECT` input state is asking for: `task`
(`CardSelectTask`), `can_pick_zero`, `can_pick_any_number`, `pick_count`,
`cards` (the offered `CardId`s for DISCOVERY/CODEX tasks).

### `DamageInfo`

`damage`, `attack_count`.

---

## Enums

### `GameOutcome`
`UNDECIDED`, `PLAYER_VICTORY`, `PLAYER_LOSS`

### `BattleOutcome`  (C++ `sts::Outcome`)
`UNDECIDED`, `PLAYER_VICTORY`, `PLAYER_LOSS`

### `ActionType`
`CARD`, `POTION`, `SINGLE_CARD_SELECT`, `MULTI_CARD_SELECT`, `END_TURN`

### `RewardsActionType`  (C++ `search::GameAction::RewardsActionType`)
`CARD`, `GOLD`, `KEY`, `POTION`, `RELIC`, `CARD_REMOVE`, `SKIP`

### `InputState`
Only `PLAYER_NORMAL` and `CARD_SELECT` appear at decision points; the rest are
internal engine states.
```
EXECUTING_ACTIONS, PLAYER_NORMAL, CARD_SELECT, CHOOSE_STANCE_ACTION,
CHOOSE_TOOLBOX_COLORLESS_CARD, CHOOSE_EXHAUST_POTION_CARDS,
CHOOSE_GAMBLING_CARDS, CHOOSE_ENTROPIC_BREW_DISCARD_POTIONS,
CHOOSE_DISCARD_CARDS, SCRY, SELECT_ENEMY_ACTIONS, FILL_RANDOM_POTIONS,
SHUFFLE_INTO_DRAW_BURN, SHUFFLE_INTO_DRAW_VOID, SHUFFLE_INTO_DRAW_DAZED,
SHUFFLE_INTO_DRAW_WOUND, SHUFFLE_INTO_DRAW_SLIMED,
SHUFFLE_INTO_DRAW_ALL_STATUS, SHUFFLE_CUR_CARD_INTO_DRAW,
SHUFFLE_DISCARD_TO_DRAW, INITIAL_SHUFFLE, CREATE_RANDOM_CARD_IN_HAND_POWER,
CREATE_RANDOM_CARD_IN_HAND_COLORLESS, CREATE_RANDOM_CARD_IN_HAND_DEAD_BRANCH,
SELECT_CARD_IN_HAND_EXHAUST, GENERATE_NILRY_CARDS,
EXHAUST_RANDOM_CARD_IN_HAND, SELECT_STRANGE_SPOON_PROC,
SELECT_ENEMY_THE_SPECIMEN_APPLY_POISON, SELECT_WARPED_TONGS_CARD,
CREATE_ENCHIRIDION_POWER, SELECT_CONFUSED_CARD_COST
```

### `CardSelectTask`
```
INVALID, ARMAMENTS, CODEX, DISCOVERY, DUAL_WIELD, EXHAUST_ONE, EXHAUST_MANY,
EXHUME, FORETHOUGHT, GAMBLE, HEADBUTT, HOLOGRAM, LIQUID_MEMORIES_POTION,
MEDITATE, NIGHTMARE, RECYCLE, SECRET_TECHNIQUE, SECRET_WEAPON, SEEK, SETUP,
WARCRY
```

### `Stance`
`NEUTRAL`, `CALM`, `WRATH`, `DIVINITY`

### `PlayerStatus`
```
INVALID, DOUBLE_DAMAGE, DRAW_REDUCTION, FRAIL, INTANGIBLE, VULNERABLE, WEAK,
BIAS, CONFUSED, CONSTRICTED, ENTANGLED, FASTING, HEX, LOSE_DEXTERITY,
LOSE_STRENGTH, NO_BLOCK, NO_DRAW, WRAITH_FORM, BARRICADE, BLASPHEMER,
CORRUPTION, ELECTRO, SURROUNDED, MASTER_REALITY, PEN_NIB, WRATH_NEXT_TURN,
AMPLIFY, BLUR, BUFFER, COLLECT, DOUBLE_TAP, DUPLICATION, ECHO_FORM,
FREE_ATTACK_POWER, REBOUND, MANTRA, ACCURACY, AFTER_IMAGE, BATTLE_HYMN,
BRUTALITY, BURST, COMBUST, CREATIVE_AI, DARK_EMBRACE, DEMON_FORM, DEVA,
DEVOTION, DRAW_CARD_NEXT_TURN, ENERGIZED, ENVENOM, ESTABLISHMENT, EVOLVE,
FEEL_NO_PAIN, FIRE_BREATHING, FLAME_BARRIER, FOCUS, FORESIGHT, HELLO_WORLD,
INFINITE_BLADES, JUGGERNAUT, LIKE_WATER, LOOP, MAGNETISM, MAYHEM, METALLICIZE,
NEXT_TURN_BLOCK, NOXIOUS_FUMES, OMEGA, PANACHE, PHANTASMAL, PLATED_ARMOR,
RAGE, REGEN, RITUAL, RUPTURE, SADISTIC, STATIC_DISCHARGE, THORNS,
THOUSAND_CUTS, TOOLS_OF_THE_TRADE, VIGOR, WAVE_OF_THE_HAND, EQUILIBRIUM,
ARTIFACT, DEXTERITY, STRENGTH, THE_BOMB
```

### `MonsterStatus`
```
ARTIFACT, BLOCK_RETURN, CHOKED, CORPSE_EXPLOSION, LOCK_ON, MARK, METALLICIZE,
PLATED_ARMOR, POISON, REGEN, SHACKLED, STRENGTH, VULNERABLE, WEAK, ANGRY,
BEAT_OF_DEATH, CURIOSITY, CURL_UP, ENRAGE, FADING, FLIGHT,
GENERIC_STRENGTH_UP, INTANGIBLE, MALLEABLE, MODE_SHIFT, RITUAL, SLOW,
SPORE_CLOUD, THIEVERY, THORNS, TIME_WARP, INVINCIBLE, REACTIVE, SHARP_HIDE,
ASLEEP, BARRICADE, MINION, MINION_LEADER, PAINFUL_STABS, REGROW, SHIFTING,
STASIS, INVALID
```

### `MonsterId`
```
INVALID, ACID_SLIME_L, ACID_SLIME_M, ACID_SLIME_S, AWAKENED_ONE, BEAR,
BLUE_SLAVER, BOOK_OF_STABBING, BRONZE_AUTOMATON, BRONZE_ORB, BYRD, CENTURION,
CHOSEN, CORRUPT_HEART, CULTIST, DAGGER, DARKLING, DECA, DONU, EXPLODER,
FAT_GREMLIN, FUNGI_BEAST, GIANT_HEAD, GREEN_LOUSE, GREMLIN_LEADER,
GREMLIN_NOB, GREMLIN_WIZARD, HEXAGHOST, JAW_WORM, LAGAVULIN, LOOTER,
MAD_GREMLIN, MUGGER, MYSTIC, NEMESIS, ORB_WALKER, POINTY, RED_LOUSE,
RED_SLAVER, REPTOMANCER, REPULSOR, ROMEO, SENTRY, SHELLED_PARASITE,
SHIELD_GREMLIN, SLIME_BOSS, SNAKE_PLANT, SNEAKY_GREMLIN, SNECKO,
SPHERIC_GUARDIAN, SPIKER, SPIKE_SLIME_L, SPIKE_SLIME_M, SPIKE_SLIME_S,
SPIRE_GROWTH, SPIRE_SHIELD, SPIRE_SPEAR, TASKMASTER, THE_CHAMP,
THE_COLLECTOR, THE_GUARDIAN, THE_MAW, TIME_EATER, TORCH_HEAD, TRANSIENT,
WRITHING_MASS
```

### `MonsterMoveId`
One value per monster move (197 values, e.g. `JAW_WORM_CHOMP`,
`CULTIST_INCANTATION`, `GREMLIN_NOB_BELLOW`) — names mirror the C++ enum in
`sts_lightspeed/include/constants/MonsterMoves.h`. `Monster.move_id` is the
monster's intent.

### `Potion`
```
INVALID, EMPTY_POTION_SLOT, AMBROSIA, ANCIENT_POTION, ATTACK_POTION,
BLESSING_OF_THE_FORGE, BLOCK_POTION, BLOOD_POTION, BOTTLED_MIRACLE,
COLORLESS_POTION, CULTIST_POTION, CUNNING_POTION, DEXTERITY_POTION,
DISTILLED_CHAOS, DUPLICATION_POTION, ELIXIR_POTION, ENERGY_POTION,
ENTROPIC_BREW, ESSENCE_OF_DARKNESS, ESSENCE_OF_STEEL, EXPLOSIVE_POTION,
FAIRY_POTION, FEAR_POTION, FIRE_POTION, FLEX_POTION, FOCUS_POTION,
FRUIT_JUICE, GAMBLERS_BREW, GHOST_IN_A_JAR, HEART_OF_IRON, LIQUID_BRONZE,
LIQUID_MEMORIES, POISON_POTION, POTION_OF_CAPACITY, POWER_POTION,
REGEN_POTION, SKILL_POTION, SMOKE_BOMB, SNECKO_OIL, SPEED_POTION,
STANCE_POTION, STRENGTH_POTION, SWIFT_POTION, WEAK_POTION
```

### `ScreenState`
`INVALID`, `EVENT_SCREEN`, `REWARDS`, `BOSS_RELIC_REWARDS`, `CARD_SELECT`,
`MAP_SCREEN`, `TREASURE_ROOM`, `REST_ROOM`, `SHOP_ROOM`, `BATTLE`

### `Event`
Which event is active (`gc.cur_event`) while `screen_state == EVENT_SCREEN`.
The first five values are internal room markers, not real events:
```
INVALID, MONSTER, REST, SHOP, TREASURE, NEOW, OMINOUS_FORGE, PLEADING_VAGRANT,
ANCIENT_WRITING, OLD_BEGGAR, BIG_FISH, BONFIRE_SPIRITS, COLOSSEUM, CURSED_TOME,
DEAD_ADVENTURER, DESIGNER_IN_SPIRE, AUGMENTER, DUPLICATOR, FACE_TRADER, FALLING,
FORGOTTEN_ALTAR, THE_DIVINE_FOUNTAIN, GHOSTS, GOLDEN_IDOL, GOLDEN_SHRINE,
WING_STATUE, KNOWING_SKULL, LAB, THE_SSSSSERPENT, LIVING_WALL, MASKED_BANDITS,
MATCH_AND_KEEP, MINDBLOOM, HYPNOTIZING_COLORED_MUSHROOMS, MYSTERIOUS_SPHERE,
THE_NEST, NLOTH, NOTE_FOR_YOURSELF, PURIFIER, SCRAP_OOZE, SECRET_PORTAL,
SENSORY_STONE, SHINING_LIGHT, THE_CLERIC, THE_JOUST, THE_LIBRARY, THE_MAUSOLEUM,
THE_MOAI_HEAD, THE_WOMAN_IN_BLUE, TOMB_OF_LORD_RED_MASK, TRANSMORGRIFIER,
UPGRADE_SHRINE, VAMPIRES, WE_MEET_AGAIN, WHEEL_OF_CHANGE, WINDING_HALLS,
WORLD_OF_GOOP
```
`COLOSSEUM` and `MATCH_AND_KEEP` are compile-time disabled in the engine
(`GameContext::disableColosseum` / `disableMatchAndKeep`) and never spawn.
`BONFIRE_SPIRITS` and `LAB` skip the option screen (card select / rewards
open directly).

### `NeowBonus` / `NeowDrawback` / `NeowOption`
`gc.neow_rewards` returns 4 `NeowOption`s, each with `bonus` (`NeowBonus`),
`drawback` (`NeowDrawback`), and ready-made text in `bonus_text` /
`drawback_text` (from the C++ `Neow::bonusStrings`/`drawbackStrings`).
Option 0 never has a drawback; option 3 is always a boss-relic trade.

### `CharacterClass`
`IRONCLAD`, `SILENT`, `DEFECT`, `WATCHER`, `INVALID`
*(engine is Ironclad-complete; others are partial.)*

### `Room`
`SHOP`, `REST`, `EVENT`, `ELITE`, `MONSTER`, `TREASURE`, `BOSS`,
`BOSS_TREASURE`, `NONE`, `INVALID`

### `CardRarity`
`COMMON`, `UNCOMMON`, `RARE`, `BASIC`, `SPECIAL`, `CURSE`, `INVALID`

### `CardColor`
`RED`, `GREEN`, `PURPLE`, `COLORLESS`, `CURSE`, `INVALID`

### `CardType`
`ATTACK`, `SKILL`, `POWER`, `CURSE`, `STATUS`, `INVALID`

### `CardId`
All cards across every character + colorless + curses + statuses (the binding
exposes the full enum). Values (alphabetical, as bound):

```
INVALID, ACCURACY, ACROBATICS, ADRENALINE, AFTER_IMAGE, AGGREGATE, ALCHEMIZE,
ALL_FOR_ONE, ALL_OUT_ATTACK, ALPHA, AMPLIFY, ANGER, APOTHEOSIS, APPARITION,
ARMAMENTS, ASCENDERS_BANE, AUTO_SHIELDS, A_THOUSAND_CUTS, BACKFLIP, BACKSTAB,
BALL_LIGHTNING, BANDAGE_UP, BANE, BARRAGE, BARRICADE, BASH, BATTLE_HYMN,
BATTLE_TRANCE, BEAM_CELL, BECOME_ALMIGHTY, BERSERK, BETA, BIASED_COGNITION,
BITE, BLADE_DANCE, BLASPHEMY, BLIND, BLIZZARD, BLOODLETTING, BLOOD_FOR_BLOOD,
BLUDGEON, BLUR, BODY_SLAM, BOOT_SEQUENCE, BOUNCING_FLASK, BOWLING_BASH,
BRILLIANCE, BRUTALITY, BUFFER, BULLET_TIME, BULLSEYE, BURN, BURNING_PACT,
BURST, CALCULATED_GAMBLE, CALTROPS, CAPACITOR, CARNAGE, CARVE_REALITY,
CATALYST, CHAOS, CHARGE_BATTERY, CHILL, CHOKE, CHRYSALIS, CLASH, CLAW, CLEAVE,
CLOAK_AND_DAGGER, CLOTHESLINE, CLUMSY, COLD_SNAP, COLLECT, COMBUST,
COMPILE_DRIVER, CONCENTRATE, CONCLUDE, CONJURE_BLADE, CONSECRATE, CONSUME,
COOLHEADED, CORE_SURGE, CORPSE_EXPLOSION, CORRUPTION, CREATIVE_AI, CRESCENDO,
CRIPPLING_CLOUD, CRUSH_JOINTS, CURSE_OF_THE_BELL, CUT_THROUGH_FATE,
DAGGER_SPRAY, DAGGER_THROW, DARKNESS, DARK_EMBRACE, DARK_SHACKLES, DASH, DAZED,
DEADLY_POISON, DECAY, DECEIVE_REALITY, DEEP_BREATH, DEFEND_BLUE, DEFEND_GREEN,
DEFEND_PURPLE, DEFEND_RED, DEFLECT, DEFRAGMENT, DEMON_FORM, DEUS_EX_MACHINA,
DEVA_FORM, DEVOTION, DIE_DIE_DIE, DISARM, DISCOVERY, DISTRACTION, DODGE_AND_ROLL,
DOOM_AND_GLOOM, DOPPELGANGER, DOUBLE_ENERGY, DOUBLE_TAP, DOUBT,
DRAMATIC_ENTRANCE, DROPKICK, DUALCAST, DUAL_WIELD, ECHO_FORM, ELECTRODYNAMICS,
EMPTY_BODY, EMPTY_FIST, EMPTY_MIND, ENDLESS_AGONY, ENLIGHTENMENT, ENTRENCH,
ENVENOM, EQUILIBRIUM, ERUPTION, ESCAPE_PLAN, ESTABLISHMENT, EVALUATE,
EVISCERATE, EVOLVE, EXHUME, EXPERTISE, EXPUNGER, FAME_AND_FORTUNE, FASTING,
FEAR_NO_EVIL, FEED, FEEL_NO_PAIN, FIEND_FIRE, FINESSE, FINISHER, FIRE_BREATHING,
FISSION, FLAME_BARRIER, FLASH_OF_STEEL, FLECHETTES, FLEX, FLURRY_OF_BLOWS,
FLYING_KNEE, FLYING_SLEEVES, FOLLOW_UP, FOOTWORK, FORCE_FIELD,
FOREIGN_INFLUENCE, FORESIGHT, FORETHOUGHT, FTL, FUSION, GENETIC_ALGORITHM,
GHOSTLY_ARMOR, GLACIER, GLASS_KNIFE, GOOD_INSTINCTS, GO_FOR_THE_EYES,
GRAND_FINALE, HALT, HAND_OF_GREED, HAVOC, HEADBUTT, HEATSINKS, HEAVY_BLADE,
HEEL_HOOK, HELLO_WORLD, HEMOKINESIS, HOLOGRAM, HYPERBEAM, IMMOLATE, IMPATIENCE,
IMPERVIOUS, INDIGNATION, INFERNAL_BLADE, INFINITE_BLADES, INFLAME, INJURY,
INNER_PEACE, INSIGHT, INTIMIDATE, IRON_WAVE, JAX, JACK_OF_ALL_TRADES, JUDGMENT,
JUGGERNAUT, JUST_LUCKY, LEAP, LEG_SWEEP, LESSON_LEARNED, LIKE_WATER,
LIMIT_BREAK, LIVE_FOREVER, LOOP, MACHINE_LEARNING, MADNESS, MAGNETISM, MALAISE,
MASTERFUL_STAB, MASTER_OF_STRATEGY, MASTER_REALITY, MAYHEM, MEDITATE, MELTER,
MENTAL_FORTRESS, METALLICIZE, METAMORPHOSIS, METEOR_STRIKE, MIND_BLAST, MIRACLE,
MULTI_CAST, NECRONOMICURSE, NEUTRALIZE, NIGHTMARE, NIRVANA, NORMALITY,
NOXIOUS_FUMES, OFFERING, OMEGA, OMNISCIENCE, OUTMANEUVER, OVERCLOCK, PAIN,
PANACEA, PANACHE, PANIC_BUTTON, PARASITE, PERFECTED_STRIKE, PERSEVERANCE,
PHANTASMAL_KILLER, PIERCING_WAIL, POISONED_STAB, POMMEL_STRIKE, POWER_THROUGH,
PRAY, PREDATOR, PREPARED, PRESSURE_POINTS, PRIDE, PROSTRATE, PROTECT, PUMMEL,
PURITY, QUICK_SLASH, RAGE, RAGNAROK, RAINBOW, RAMPAGE, REACH_HEAVEN, REAPER,
REBOOT, REBOUND, RECKLESS_CHARGE, RECURSION, RECYCLE, REFLEX, REGRET,
REINFORCED_BODY, REPROGRAM, RIDDLE_WITH_HOLES, RIP_AND_TEAR, RITUAL_DAGGER,
RUPTURE, RUSHDOWN, SADISTIC_NATURE, SAFETY, SANCTITY, SANDS_OF_TIME, SASH_WHIP,
SCRAPE, SCRAWL, SEARING_BLOW, SECOND_WIND, SECRET_TECHNIQUE, SECRET_WEAPON,
SEEING_RED, SEEK, SELF_REPAIR, SENTINEL, SETUP, SEVER_SOUL, SHAME, SHIV,
SHOCKWAVE, SHRUG_IT_OFF, SIGNATURE_MOVE, SIMMERING_FURY, SKEWER, SKIM, SLICE,
SLIMED, SMITE, SNEAKY_STRIKE, SPIRIT_SHIELD, SPOT_WEAKNESS, STACK,
STATIC_DISCHARGE, STEAM_BARRIER, STORM, STORM_OF_STEEL, STREAMLINE, STRIKE_BLUE,
STRIKE_GREEN, STRIKE_PURPLE, STRIKE_RED, STUDY, SUCKER_PUNCH, SUNDER, SURVIVOR,
SWEEPING_BEAM, SWIFT_STRIKE, SWIVEL, SWORD_BOOMERANG, TACTICIAN,
TALK_TO_THE_HAND, TANTRUM, TEMPEST, TERROR, THE_BOMB, THINKING_AHEAD, THIRD_EYE,
THROUGH_VIOLENCE, THUNDERCLAP, THUNDER_STRIKE, TOOLS_OF_THE_TRADE, TRANQUILITY,
TRANSMUTATION, TRIP, TRUE_GRIT, TURBO, TWIN_STRIKE, UNLOAD, UPPERCUT, VAULT,
VIGILANCE, VIOLENCE, VOID, WALLOP, WARCRY, WAVE_OF_THE_HAND, WEAVE,
WELL_LAID_PLANS, WHEEL_KICK, WHIRLWIND, WHITE_NOISE, WILD_STRIKE,
WINDMILL_STRIKE, WISH, WORSHIP, WOUND, WRAITH_FORM, WREATH_OF_FLAME, WRITHE, ZAP
```

### `MonsterEncounter`  (bound name; C++ alias `ME`)
```
INVALID, CULTIST, JAW_WORM, TWO_LOUSE, SMALL_SLIMES, BLUE_SLAVER, GREMLIN_GANG,
LOOTER, LARGE_SLIME, LOTS_OF_SLIMES, EXORDIUM_THUGS, EXORDIUM_WILDLIFE,
RED_SLAVER, THREE_LOUSE, TWO_FUNGI_BEASTS, GREMLIN_NOB, LAGAVULIN,
THREE_SENTRIES, SLIME_BOSS, THE_GUARDIAN, HEXAGHOST, SPHERIC_GUARDIAN, CHOSEN,
SHELL_PARASITE, THREE_BYRDS, TWO_THIEVES, CHOSEN_AND_BYRDS, SENTRY_AND_SPHERE,
SNAKE_PLANT, SNECKO, CENTURION_AND_HEALER, CULTIST_AND_CHOSEN, THREE_CULTIST,
SHELLED_PARASITE_AND_FUNGI, GREMLIN_LEADER, SLAVERS, BOOK_OF_STABBING,
AUTOMATON, COLLECTOR, CHAMP, THREE_DARKLINGS, ORB_WALKER, THREE_SHAPES,
SPIRE_GROWTH, TRANSIENT, FOUR_SHAPES, MAW, SPHERE_AND_TWO_SHAPES, JAW_WORM_HORDE,
WRITHING_MASS, GIANT_HEAD, NEMESIS, REPTOMANCER, AWAKENED_ONE, TIME_EATER,
DONU_AND_DECA, SHIELD_AND_SPEAR, THE_HEART, LAGAVULIN_EVENT,
COLOSSEUM_EVENT_SLAVERS, COLOSSEUM_EVENT_NOBS, MASKED_BANDITS_EVENT,
MUSHROOMS_EVENT, MYSTERIOUS_SPHERE_EVENT
```
The 10 act-bosses recognized by `NNInterface` one-hot encoding are: `SLIME_BOSS`,
`HEXAGHOST`, `THE_GUARDIAN`, `CHAMP`, `AUTOMATON`, `COLLECTOR`, `TIME_EATER`,
`DONU_AND_DECA`, `AWAKENED_ONE`, `THE_HEART`.

### `RelicId`
```
AKABEKO, ART_OF_WAR, BIRD_FACED_URN, BLOODY_IDOL, BLUE_CANDLE, BRIMSTONE,
CALIPERS, CAPTAINS_WHEEL, CENTENNIAL_PUZZLE, CERAMIC_FISH, CHAMPION_BELT,
CHARONS_ASHES, CHEMICAL_X, CLOAK_CLASP, DARKSTONE_PERIAPT, DEAD_BRANCH, DUALITY,
ECTOPLASM, EMOTION_CHIP, FROZEN_CORE, FROZEN_EYE, GAMBLING_CHIP, GINGER,
GOLDEN_EYE, GREMLIN_HORN, HAND_DRILL, HAPPY_FLOWER, HORN_CLEAT, HOVERING_KITE,
ICE_CREAM, INCENSE_BURNER, INK_BOTTLE, INSERTER, KUNAI, LETTER_OPENER,
LIZARD_TAIL, MAGIC_FLOWER, MARK_OF_THE_BLOOM, MEDICAL_KIT, MELANGE,
MERCURY_HOURGLASS, MUMMIFIED_HAND, NECRONOMICON, NILRYS_CODEX, NUNCHAKU,
ODD_MUSHROOM, OMAMORI, ORANGE_PELLETS, ORICHALCUM, ORNAMENTAL_FAN, PAPER_KRANE,
PAPER_PHROG, PEN_NIB, PHILOSOPHERS_STONE, POCKETWATCH, RED_SKULL, RUNIC_CUBE,
RUNIC_DOME, RUNIC_PYRAMID, SACRED_BARK, SELF_FORMING_CLAY, SHURIKEN, SNECKO_EYE,
SNECKO_SKULL, SOZU, STONE_CALENDAR, STRANGE_SPOON, STRIKE_DUMMY, SUNDIAL,
THE_ABACUS, THE_BOOT, THE_SPECIMEN, TINGSHA, TOOLBOX, TORII, TOUGH_BANDAGES,
TOY_ORNITHOPTER, TUNGSTEN_ROD, TURNIP, TWISTED_FUNNEL, UNCEASING_TOP,
VELVET_CHOKER, VIOLET_LOTUS, WARPED_TONGS, WRIST_BLADE, BLACK_BLOOD,
BURNING_BLOOD, MEAT_ON_THE_BONE, FACE_OF_CLERIC, ANCHOR, ANCIENT_TEA_SET,
BAG_OF_MARBLES, BAG_OF_PREPARATION, BLOOD_VIAL, BOTTLED_FLAME, BOTTLED_LIGHTNING,
BOTTLED_TORNADO, BRONZE_SCALES, BUSTED_CROWN, CLOCKWORK_SOUVENIR, COFFEE_DRIPPER,
CRACKED_CORE, CURSED_KEY, DAMARU, DATA_DISK, DU_VU_DOLL, ENCHIRIDION,
FOSSILIZED_HELIX, FUSION_HAMMER, GIRYA, GOLD_PLATED_CABLES, GREMLIN_VISAGE,
HOLY_WATER, LANTERN, MARK_OF_PAIN, MUTAGENIC_STRENGTH, NEOWS_LAMENT, NINJA_SCROLL,
NUCLEAR_BATTERY, ODDLY_SMOOTH_STONE, PANTOGRAPH, PRESERVED_INSECT, PURE_WATER,
RED_MASK, RING_OF_THE_SERPENT, RING_OF_THE_SNAKE, RUNIC_CAPACITOR, SLAVERS_COLLAR,
SLING_OF_COURAGE, SYMBIOTIC_VIRUS, TEARDROP_LOCKET, THREAD_AND_NEEDLE, VAJRA,
ASTROLABE, BLACK_STAR, CALLING_BELL, CAULDRON, CULTIST_HEADPIECE, DOLLYS_MIRROR,
DREAM_CATCHER, EMPTY_CAGE, ETERNAL_FEATHER, FROZEN_EGG, GOLDEN_IDOL, JUZU_BRACELET,
LEES_WAFFLE, MANGO, MATRYOSHKA, MAW_BANK, MEAL_TICKET, MEMBERSHIP_CARD, MOLTEN_EGG,
NLOTHS_GIFT, NLOTHS_HUNGRY_FACE, OLD_COIN, ORRERY, PANDORAS_BOX, PEACE_PIPE, PEAR,
POTION_BELT, PRAYER_WHEEL, PRISMATIC_SHARD, QUESTION_CARD, REGAL_PILLOW,
SSSERPENT_HEAD, SHOVEL, SINGING_BOWL, SMILING_MASK, SPIRIT_POOP, STRAWBERRY,
THE_COURIER, TINY_CHEST, TINY_HOUSE, TOXIC_EGG, WAR_PAINT, WHETSTONE,
WHITE_BEAST_STATUE, WING_BOOTS, CIRCLET, RED_CIRCLET, INVALID
```

---

## Typical usage sketch

```python
from env.game_interface import sts

gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed=42, ascension=0)

agent = sts.Agent()
agent.pause_on_card_reward = True   # stop so we can choose cards ourselves
agent.print_logs = False

agent.playout(gc)                   # advances the run until a pause / end

if gc.screen_state == sts.ScreenState.REWARDS:
    choices = gc.get_card_reward()  # list[Card]
    if choices:
        gc.pick_reward_card(choices[0])
    else:
        gc.skip_reward_cards()

# encode for an NN
nn = sts.getNNInterface()
obs = nn.getObservation(gc)         # length-412 list[int]
maxs = nn.getObservationMaximums()

print(gc.outcome, gc.floor_num, gc.cur_hp, "/", gc.max_hp)
print([str(c) for c in gc.deck])
```

---

## Gotchas

- `deck` and `relics` return **copies** — write to the deck via
  `obtain_card`/`remove_card`, not by mutating the returned list.
- The reward helpers (`get_card_reward`, `pick_reward_card`, `skip_reward_cards`)
  only work while `screen_state == ScreenState.REWARDS` **and** there is a pending
  card reward; otherwise they warn to stderr and do nothing.
- Combat **is** steppable from Python via `BattleContext` + `Action` (see the
  Combat section). `Action.execute` / `GameAction.execute` raise `ValueError`
  on illegal actions instead of hitting engine asserts.
- `bc.legal_actions()` can return `[]` while `outcome == UNDECIDED` on
  card-select states of non-Ironclad cards (Hologram/Meditate/Nightmare/
  Recycle/Setup/Seek) — treat that as an error, don't loop on it.
- Combat state views (`bc.player`, `bc.monsters`, `bc.cards`) are live;
  the lists they hand out (`hand`, piles, `potions`) are copies.
- ABI constraint: the `.pyd` only imports from MSYS2's MinGW64 Python 3.14 (see
  `memory/build-run-slaythespire.md`). The pybind11 submodule must be ≥ v3.0
  for Python 3.14, and configuring needs `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`
  with CMake ≥ 4.
