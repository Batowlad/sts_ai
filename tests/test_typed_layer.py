"""Tests for the typed state/action layer.

Covers the dataclasses in `env/game_types.py`, the builders in `env/observe.py`, the pure
renderer in `env/render.py`, `step()` taking an `ActionOption` or a key, the structured
action dialect in `env/action_parser.py`, and the pydantic models behind `game_data/`
and `configs/`.

Run with the MSYS2 mingw64 python (see memory/build-run-slaythespire.md):
    python tests/test_typed_layer.py [seed] [max_steps]
"""
import json
import random
import sys
import tempfile
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configs.config import load_config
from env.action_parser import (
    ActionFormatError,
    get_func_words,
    get_funcs,
    parse_action,
    parse_structured_action,
)
from env.game_interface import GameInterface, _card_name, sts
from env.game_types import (
    ActionKind,
    ActionOption,
    CardView,
    CombatView,
    Observation,
    PlayerView,
)
from env.render import render, render_action_options
from env.state_encoder import encode_state
from game_data.schemas import PotionEntry, load_table


def _raises(exc_type, fn, *args, match=""):
    """Assert that fn(*args) raises exc_type with `match` somewhere in the message."""
    try:
        fn(*args)
    except exc_type as exc:
        assert match in str(exc), exc
    else:
        raise AssertionError(f"{fn.__name__}{args} did not raise {exc_type.__name__}")


def _obs(**fields) -> Observation:
    """An Observation with throwaway vitals, for the renderer tests."""
    vitals = dict(screen="TREASURE_ROOM", floor=1, act=1, cur_hp=40, max_hp=80, gold=0,
                  outcome="UNDECIDED")
    return Observation(**{**vitals, **fields})


def test_module_identity():
    """`env.game_types` and the flat `game_types` must be one module, not two.

    The env package imports its siblings flat while callers outside use the package
    path. Without the alias in `env/__init__.py`, Python builds two of every class and
    `isinstance(opt, ActionOption)` inside `step()` silently fails for options built
    through the other name.
    """
    import game_types
    import env.game_types

    assert game_types is env.game_types
    assert game_types.ActionOption is ActionOption


def test_types_are_frozen():
    opt = ActionOption(index=0, kind=ActionKind.END_TURN, label="end turn")
    _raises(FrozenInstanceError, setattr, opt, "index", 3)


def test_action_key_is_position_independent():
    """The same decision from two different steps shares a key; the index differs."""
    a = ActionOption(index=0, kind=ActionKind.PLAY_CARD, label="", card_id="BASH", target_idx=0)
    b = ActionOption(index=7, kind=ActionKind.PLAY_CARD, label="", card_id="BASH", target_idx=0)
    assert a.key == b.key == "play_card:BASH->0" and a != b
    assert ActionOption(index=1, kind=ActionKind.MAP_MOVE, label="", idx1=3).key == "map_move:3"
    assert ActionOption(index=1, kind=ActionKind.END_TURN, label="").key == "end_turn"


def test_card_name_from_id():
    """observe.py names cards from the id string; the '+' must survive that path."""
    assert _card_name("BASH", True) == "Bash+"
    assert _card_name("BASH", False) == "Bash"


def test_render_needs_no_engine():
    """`render` takes only an Observation - including for a screen with no block of its
    own, where the old string encoder returned None."""
    deck = (CardView(id="BASH", name="Bash"), *[CardView(id="STRIKE_RED", name="Strike")] * 2)
    text = render(_obs(screen="WEIRD_NEW_SCREEN", deck=deck))
    assert text.startswith("Screen: WEIRD_NEW_SCREEN")
    assert "HP: 40/80" in text and "2x Strike" in text and "1x Bash" in text


def test_draw_pile_order_is_hidden_by_default():
    """Order is information a player does not have; contents are."""
    combat = CombatView(
        turn=1, encounter="CULTIST", outcome="UNDECIDED", input_state="PLAYER_NORMAL",
        player=PlayerView(cur_hp=50, max_hp=80, block=0, energy=3),
        draw_pile=(CardView(id="BASH", name="Bash"), CardView(id="STRIKE_RED", name="Strike")),
    )
    obs = _obs(screen="BATTLE", combat=combat)
    assert "Draw pile contents:" in render(obs)
    assert "Draw pile (order):" in render(obs, reveal_draw_pile=True)


def test_render_action_options():
    """Keys, not indices, and one line per distinct decision."""
    opts = (ActionOption(index=0, kind=ActionKind.SKIP, label="skip"),
            ActionOption(index=1, kind=ActionKind.TAKE_REWARD, label="take card: Bash"))
    text = render_action_options(opts, "REWARDS")
    assert text.startswith("Legal actions (You can only select one card/relic):")
    assert '- "skip" - skip' in text and '- "take_reward" - take card: Bash' in text
    assert '{"action": "<key>"}' in text
    assert "0." not in text and "1." not in text      # an index in the prompt invites one back
    assert render_action_options((), "MAP_SCREEN") == "No legal actions on this screen."


def test_render_collapses_duplicate_keys():
    """Two identical Strikes at one target are one decision, so one line."""
    strike = dict(kind=ActionKind.PLAY_CARD, label="play Strike on Cultist",
                  card_id="STRIKE_RED", target_idx=0)
    text = render_action_options((ActionOption(index=0, **strike),
                                 ActionOption(index=1, **strike)))
    assert text.count("play Strike on Cultist") == 1


def test_parser_ignores_typed_api():
    """legal_action_options()/observe() return dataclasses, so the NL parser must not
    dispatch to them - and 'legal' must still reach legal_actions()."""
    assert not {"legal_action_options", "observe"} & set(get_funcs())
    words = get_func_words()
    assert words["legal"] == "legal_actions" and "options" not in words


def test_game_data_is_validated():
    """A malformed generated table fails loudly, naming the entry."""
    good = {"name": "Fire Potion", "rarity": "COMMON", "requires_target": True, "text": "x"}
    missing_flag = {"name": "Busted", "rarity": "COMMON", "text": "x"}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.json"
        path.write_text(json.dumps({"FIRE_POTION": good, "BUSTED": missing_flag}))
        _raises(ValueError, load_table, path, PotionEntry, match="BUSTED")
        path.write_text(json.dumps({"FIRE_POTION": {**good, "typo_key": 1}}))
        _raises(ValueError, load_table, path, PotionEntry, match="FIRE_POTION")


def test_real_tables_load_as_models():
    from game_data.card_data.card_text import CARD_DATA
    from game_data.potion_data.potion_text import POTION_DATA
    from game_data.relic_data.relic_text import RELIC_DATA
    from game_data.status_data.status_text import MONSTER_STATUS_DATA, PLAYER_STATUS_DATA

    assert len(CARD_DATA) == 145 and CARD_DATA["BASH"].name == "Bash"
    assert len(RELIC_DATA) == 149 and RELIC_DATA["BURNING_BLOOD"].rarity == "STARTER"
    assert len(POTION_DATA) == 33 and POTION_DATA["FIRE_POTION"].requires_target
    assert len(PLAYER_STATUS_DATA) == 86 and len(MONSTER_STATUS_DATA) == 42
    assert PLAYER_STATUS_DATA["VULNERABLE"].stacks is True


def test_config_is_validated():
    cfg = load_config()
    assert cfg.env.character == "IRONCLAD" and cfg.rollout.max_steps > 0
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.yaml"
        bad.write_text("env:\n  ascension: 99\n")
        _raises(ValueError, load_config, bad, match="ascension")   # out of range
        bad.write_text("env:\n  sed: 42\n")
        _raises(ValueError, load_config, bad, match="sed")         # typo for 'seed'


def test_stale_option_is_rejected():
    """An option from another screen must not run just because its bits decode there."""
    gi = GameInterface()
    stale = gi.legal_action_options()[0]            # a Neow option, on EVENT_SCREEN
    while gi.gc.screen_state == sts.ScreenState.EVENT_SCREEN:
        gi.step(0)
    _raises(ValueError, gi.step, stale, match="enumerated on EVENT_SCREEN")


def test_step_by_key():
    """A key resolves against the options legal now, and moves the game on."""
    gi = GameInterface()
    before = {o.key for o in gi.legal_action_options()}
    gi.step(sorted(before)[0])
    assert {o.key for o in gi.legal_action_options()} != before
    _raises(ValueError, gi.step, "play_card:BASH->0", match="not a legal action on")


def test_each_battle_starts_clean():
    """No monster from an earlier fight carries into the next one.

    Reusing one BattleContext appended every fight's monsters to the last; from the
    2nd battle on they are visible, and once past MonsterGroup's 5 slots step() broke.
    """
    gi = GameInterface()
    rng = random.Random(0)
    battles = 0
    for _ in range(200):
        if gi.gc.outcome != sts.GameOutcome.UNDECIDED:
            break
        was_in_battle = gi.bc_initiated
        gi.step(rng.choice(gi.legal_action_options()))
        if gi.bc_initiated and not was_in_battle:
            battles += 1
            leftovers = [m.name for m in gi.bc.monsters if m.is_dead_or_escaped]
            assert not leftovers, f"battle {battles} started with dead monsters {leftovers}"
    assert battles >= 2, f"only reached {battles} battles; the seed no longer covers the bug"


def test_structured_action_is_read_out_of_reasoning():
    """Free reasoning, then the commitment; a JSON example mid-thought must not win."""
    gi = GameInterface()
    key = sorted(o.key for o in gi.legal_action_options())[0]
    before = {o.key for o in gi.legal_action_options()}
    parse_structured_action(
        f'I could answer with {{"action": "something else"}}, but I will not.\n'
        f'```json\n{{"action": "{key}", "note": "reasoned"}}\n```',
        gi,
    )
    assert {o.key for o in gi.legal_action_options()} != before


def test_structured_action_errors_are_one_type():
    """Every policy-side mistake arrives as ActionFormatError, so RL can score it."""
    gi = GameInterface()
    bad = [
        ("I will play Bash.", "no JSON object"),                 # no commitment at all
        ('{"action": ""}', "malformed action object"),            # empty key
        ('{"act": "end_turn"}', "malformed action object"),       # wrong field name
        ('{"action": "end_turn", "target": 0}', "malformed action object"),  # extra field
        ('{"action": "play_card:BASH->0"}', "not a legal action on"),        # illegal here
    ]
    for text, message in bad:
        _raises(ActionFormatError, parse_structured_action, text, gi, match=message)


def test_sentence_digits_are_not_actions():
    """The old any-digit rule read 'play Bash on monster 0' as step(0). Only a bare
    number is an index now - the misparse that put actions the policy never chose into
    the reward signal."""
    taken = []

    class Recorder:
        def step(self, action):
            taken.append(action)

    for text in ("I will play Bash on monster 0 to set up the Vulnerable.",
                 "Strike the front enemy, it only has 2 hp left.",
                 "Defend. I have 3 block but the attack hits for 12."):
        _raises(ValueError, parse_action, text, Recorder(), None, match="no action could be parsed")
    assert not taken

    parse_action("  2  ", Recorder(), None)
    assert taken == [2]


def test_live_run(seed=7, max_steps=400):
    """Walk a real run, stepping by ActionOption: every decision point must yield a
    JSON-able snapshot, rendered text and well-formed options."""
    gi = GameInterface()
    rng = random.Random(seed)
    screens, kinds, steps = set(), set(), 0

    while gi.gc.outcome == sts.GameOutcome.UNDECIDED and steps < max_steps:
        obs = gi.observe()
        screens.add(obs.screen)
        json.dumps(asdict(obs))                     # a rollout log needs this to work
        assert encode_state(gi).startswith(f"Screen: {obs.screen}")

        opts = gi.legal_action_options()
        assert [o.index for o in opts] == list(range(len(opts))), obs.screen
        for o in opts:
            json.dumps(asdict(o))
            assert o.label and o.key and o.screen == obs.screen
            if o.kind in (ActionKind.USE_POTION, ActionKind.DISCARD_POTION):
                assert "Room)" not in o.label       # the room label is for map moves only
            kinds.add(o.kind)
        assert gi.legal_actions().startswith(("Legal actions", "No legal actions"))
        for o in opts:                              # every listed key must be steppable
            assert f'"{o.key}"' in gi.legal_actions()

        if not opts:
            break
        gi.step(rng.choice(opts))
        steps += 1

    assert steps > 10, "run ended too early to prove anything"
    assert {"BATTLE", "MAP_SCREEN"} <= screens
    assert {ActionKind.PLAY_CARD, ActionKind.MAP_MOVE} <= kinds
    return steps, screens, kinds


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    max_steps = int(sys.argv[2]) if len(sys.argv) > 2 else 400

    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and name != "test_live_run":
            fn()
            print(f"  ok  {name}")

    steps, screens, kinds = test_live_run(seed, max_steps)
    print(f"  ok  test_live_run: {steps} steps over {sorted(screens)}")
    print(f"      action kinds: {sorted(k.value for k in kinds)}")
    print("all typed-layer tests passed")


if __name__ == "__main__":
    main()
