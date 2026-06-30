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
| `getNNInterface()` | `getNNInterface() -> NNInterface` | Returns the singleton `NNInterface` used to encode a `GameContext` into an observation vector. |

---

## Classes

### `GameContext`
The top-level run state (map traversal / out-of-combat). Combat itself is run
internally by `Agent.playout`, not stepped from Python.

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

**Read/write fields**

| Field | Type | Default / notes |
|---|---|---|
| `outcome` | `GameOutcome` | `UNDECIDED` until win/loss. |
| `act` | `int` | 1-based act. |
| `floor_num` | `int` | |
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

> Not exposed to Python: RNG streams, relic/event/monster pools, potions,
> `map` object, and the many `chooseX`/`generateX`/combat methods on the C++
> `GameContext`. Add bindings in `slaythespire.cpp` if you need them.

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

## Enums

### `GameOutcome`
`UNDECIDED`, `PLAYER_VICTORY`, `PLAYER_LOSS`

### `ScreenState`
`INVALID`, `EVENT_SCREEN`, `REWARDS`, `BOSS_RELIC_REWARDS`, `CARD_SELECT`,
`MAP_SCREEN`, `TREASURE_ROOM`, `REST_ROOM`, `SHOP_ROOM`, `BATTLE`

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
- Combat is **not** steppable from Python — it runs inside `Agent.playout`. There
  is no `BattleContext` binding. To drive individual combat actions you'd need to
  add bindings in `slaythespire.cpp`.
- ABI constraint: the `.pyd` only imports from MSYS2's MinGW64 Python 3.14 (see
  `memory/build-run-slaythespire.md`).
