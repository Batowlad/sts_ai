# Exposing combat to Python — feasibility & plan

**Question:** what would it take to step individual combat actions from Python
(so `GameInterface.legal_actions()` / `step()` work *inside* a fight, not just at
the run level)?

**Short answer:** very doable. The engine already has a clean, discrete,
serializable action abstraction for combat (`sts::search::Action`) with
`isValidAction` / `execute` / `printDesc`. The work is almost entirely
*binding* code in `bindings/slaythespire.cpp` plus **one new ~30-line helper**
to enumerate legal actions. No engine logic needs to change.

---

## How combat actually works (the important part)

`GameContext.enter_battle` / the `BATTLE` screen state is a **stub** — it does
*not* simulate combat. It only sets `screen_state = BATTLE` and
`info.encounter`. Combat lives in a **separate `BattleContext`** object. The
canonical loop (from `ScumSearchAgent2::playout`) is:

```cpp
BattleContext bc;
bc.init(gc);                       // build combat state from gc (encounter, deck, relics, hp…)
while (bc.outcome == Outcome::UNDECIDED) {
    // pick some Action a that is valid for bc.inputState
    a.execute(bc);                 // runs the action AND drains the action queue
}
bc.exitBattle(gc);                 // writes hp/gold/relics/cards back to gc;
                                   //   on win -> gc.regainControl() -> REWARDS screen
                                   //   on loss -> gc.outcome = PLAYER_LOSS
```

So a Python combat interface mirrors exactly this: create a `BattleContext`,
`init(gc)`, expose `legal_actions(bc)` + `step(bc, action)`, and when
`bc.outcome` resolves, call `exitBattle(gc)` to hand control back to the
run-level `GameContext` (which is already bound).

### The action model (`sts::search::Action`)
A 32-bit packed value. Already has everything we need:

| Member | Meaning |
|---|---|
| `ActionType` | `CARD`, `POTION`, `SINGLE_CARD_SELECT`, `MULTI_CARD_SELECT`, `END_TURN` |
| `getSourceIdx()` | hand index (CARD) / potion slot (POTION) / select index |
| `getTargetIdx()` | monster target index; `>5` = discard potion |
| `isValidAction(bc)` | full legality check against current `BattleContext` |
| `execute(bc)` | apply + run the action queue to quiescence |
| `printDesc(os, bc)` | human-readable description (great for `__repr__`) |

`InputState` drives which actions are legal: `PLAYER_NORMAL` (play cards /
potions / end turn) vs. `CARD_SELECT` (resolve a discovery/exhaust/headbutt/…
sub-choice). `Action::isValidAction` already handles both.

### The one missing piece — legal-action enumeration
There is **no public** "give me all legal actions" function. The logic exists,
but as **private methods on `BattleScumSearcher2`**
(`enumerateActionsForNode` → `enumerateCardActions` / `enumeratePotionActions` /
`enumerateCardSelectActions`), and it writes into MCTS `Node.edges` rather than
returning a list. Two options:

1. **Write a free helper** `std::vector<Action> getLegalActions(const BattleContext&)`
   in `bindings-util.cpp` that mirrors that switch on `inputState`. ~30 lines.
   Lowest-risk, no engine changes.
2. Refactor the searcher's enumerators to fill a `std::vector<Action>&` and
   reuse them. Cleaner long-term, touches engine code.

Recommend option 1 for now. (`Action::enumerateCardSelectActions(bc)` is
*already public* and covers the `CARD_SELECT` branch, so the helper only has to
add the `PLAYER_NORMAL` card/potion/end-turn cases.)

For **out-of-combat**, the analogous `sts::search::GameAction` already has a
public `getAllActionsInState(gc)` returning `std::vector<GameAction>` — ready to
bind as-is, no helper needed.

---

## What needs binding

### Tier 1 — minimal "play a fight" loop (action stepping)
Enough to drive combat to completion from Python and read win/loss.

- **`BattleContext`** class: default ctor, `init(gc)`, `init(gc, encounter)`,
  `exit_battle(gc)`, and read-only `outcome`, `input_state`, `turn`,
  `is_battle_over`. Plus `__repr__` (the engine has `operator<<`).
- **`search::Action`**: bind ctors `(ActionType)`, `(ActionType, idx1)`,
  `(ActionType, idx1, idx2)`; `is_valid_action(bc)`, `execute(bc)`,
  accessors, and `__repr__` via `printDesc`.
- **`ActionType`**, **`Outcome`**, **`InputState`** enums.
- **`get_legal_actions(bc)`** free fn (the new helper above).
- **`GameAction`** + **`get_all_actions(gc)`** + `RewardsActionType` enum for the
  out-of-combat side (mostly free — the C++ is already public).

This tier alone makes `GameInterface.step()` / `legal_actions()` real for both
combat and run-level decisions. **Effort: ~half a day**, pure binding + 1 helper.

### Tier 2 — observations (for RL/state input)
To feed a policy you need to read combat state. Today `NNInterface.getObservation`
only takes a `GameContext` (run state) — it has **no combat encoding**. Options:

- **Expose the state structs** so Python builds its own observation:
  `Player` (curHp, maxHp, block, energy, strength, dexterity, focus, stance…),
  `MonsterGroup`/`Monster` (curHp, block, intent/move, alive), and `CardManager`
  (`hand`, `drawPile`, `discardPile`, `exhaustPile` as `CardInstance` lists).
- **Or** add a C++ `getBattleObservation(bc)` to `NNInterface` returning a fixed
  vector (consistent with the existing API).

**Caveat (the real friction):** player/monster **status effects** are stored in
bitfields + `std::map` behind **templated** accessors (`getStatus<PS::WEAK>()`),
which pybind can't bind directly. Exposing statuses needs small **non-template
wrapper getters**, e.g. `int Player::getStatusPy(PlayerStatus)`, added to the
engine (or written as free functions in `bindings-util.cpp`). Without statuses
you can still get hp/block/energy/intent — enough for a first pass.

**Effort: ~1–2 days** depending on how much status detail you want.

### Tier 3 — nice-to-haves
`CardSelectInfo` / `CardSelectTask` enum (to know *what* a `CARD_SELECT` is
asking), potion enums (`Potion`, names), monster intent decoding, and a
`BattleContext` copy constructor exposed for Python-side search/rollouts (the
C++ copy ctor is already `default`, so this is trivial and powerful for MCTS).

---

## Decisions (locked 2026-06-30)

Settled with the user; this is the agreed direction for whenever implementation
starts:

1. **Combat state lives in `BattleContext`, exposed to Python (option a).**
   `GameInterface` will hold the `BattleContext` and drive `Action.execute`.
   Less hidden state, matches the engine, and the already-`default` copy ctor
   leaves the door open for Python-side rollouts/MCTS.
2. **Observations = raw state structs (Tier 2, option a).** Bind
   `Player` / `Monster` / `MonsterGroup` / `CardManager` (+ `CardInstance`)
   fields and let Python compose its own observation vector. Accept the larger
   binding surface for feature-experimentation flexibility. This pulls in the
   templated-status-accessor problem (see Tier 2 caveat) — plan on adding small
   non-template `getStatusPy(...)` wrappers.
3. **Status now: plan only — do not implement yet.** Code is unchanged; pick up
   from this plan when ready.

**Sequencing when we start:** Tier 1 first (steppable combat: `BattleContext` +
`Action` + enums + `get_legal_actions` helper + the already-public `GameAction`
path), then Tier 2 raw-struct observations on top once the control loop runs
end-to-end.

---

## Sketch of the Tier-1 binding additions

```cpp
// bindings-util.cpp  (new helper)
namespace sts::py {
    std::vector<search::Action> getLegalActions(const BattleContext &bc) {
        std::vector<search::Action> out;
        using AT = search::ActionType;
        if (bc.outcome != Outcome::UNDECIDED) return out;

        if (bc.inputState == InputState::PLAYER_NORMAL) {
            // cards
            for (int h = 0; h < bc.cards.cardsInHand; ++h) {
                const auto &c = bc.cards.hand[h];
                if (!c.canUseOnAnyTarget(bc)) continue;
                if (c.requiresTarget()) {
                    for (int t = 0; t < bc.monsters.monsterCount; ++t)
                        if (bc.monsters.arr[t].isTargetable())
                            out.emplace_back(AT::CARD, h, t);
                } else {
                    out.emplace_back(AT::CARD, h);
                }
            }
            // potions (mirror enumeratePotionActions)
            // ...
            out.emplace_back(AT::END_TURN);

        } else if (bc.inputState == InputState::CARD_SELECT) {
            auto v = search::Action::enumerateCardSelectActions(bc); // already public
            out.insert(out.end(), v.begin(), v.end());
        }
        return out;
    }
}
```

```cpp
// slaythespire.cpp  (new bindings)
py::enum_<search::ActionType>(m, "ActionType")
    .value("CARD", search::ActionType::CARD)
    .value("POTION", search::ActionType::POTION)
    .value("SINGLE_CARD_SELECT", search::ActionType::SINGLE_CARD_SELECT)
    .value("MULTI_CARD_SELECT", search::ActionType::MULTI_CARD_SELECT)
    .value("END_TURN", search::ActionType::END_TURN);

py::enum_<Outcome>(m, "BattleOutcome") /* UNDECIDED / PLAYER_VICTORY / PLAYER_LOSS */;

py::class_<search::Action>(m, "Action")
    .def(py::init<search::ActionType>())
    .def(py::init<search::ActionType, int>())
    .def(py::init<search::ActionType, int, int>())
    .def_property_readonly("action_type", &search::Action::getActionType)
    .def_property_readonly("source_idx", &search::Action::getSourceIdx)
    .def_property_readonly("target_idx", &search::Action::getTargetIdx)
    .def("is_valid", &search::Action::isValidAction)
    .def("execute", &search::Action::execute)
    .def("__repr__", [](const search::Action &a, const BattleContext &bc){
        std::ostringstream os; a.printDesc(os, bc); return os.str(); });

py::class_<BattleContext>(m, "BattleContext")
    .def(py::init<>())
    .def("init", py::overload_cast<const GameContext&>(&BattleContext::init))
    .def("exit_battle", &BattleContext::exitBattle)
    .def_readonly("outcome", &BattleContext::outcome)
    .def_readonly("input_state", &BattleContext::inputState)
    .def_readonly("turn", &BattleContext::turn)
    .def("legal_actions", [](const BattleContext &bc){ return sts::py::getLegalActions(bc); })
    .def("__repr__", [](const BattleContext &bc){ std::ostringstream os; os<<bc; return os.str(); });
```

Then Python:

```python
gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 42, 0)
# ... advance gc until gc.screen_state == sts.ScreenState.BATTLE ...
bc = sts.BattleContext()
bc.init(gc)
while bc.outcome == sts.BattleOutcome.UNDECIDED:
    actions = bc.legal_actions()
    a = policy(bc, actions)          # your agent
    a.execute(bc)
bc.exit_battle(gc)                   # gc now on REWARDS (win) or outcome=LOSS
```

---

## Bottom line
- **Engine is ready**; combat is already a discrete `Action` MDP.
- **Tier 1** (steppable combat) ≈ half a day: bind `BattleContext` + `Action` +
  enums, write one `getLegalActions` helper, bind the already-public
  `GameAction` path. No engine changes.
- **Tier 2** (observations) ≈ 1–2 days; main snag is templated status accessors
  needing small non-template wrappers.
- Recommend exposing `BattleContext` to Python (option a) and doing Tier 1 first.
```
