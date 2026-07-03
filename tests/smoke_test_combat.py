"""End-to-end smoke test for the BattleContext / Action combat bindings.

Plays a seeded Ironclad run purely from Python: out-of-combat decisions via
GameAction, combat stepped action-by-action via BattleContext + Action with a
random policy. No MCTS agent involved.

Run with the MSYS2 mingw64 python (see memory/build-run-slaythespire.md):
    python tests/smoke_test_combat.py [seed] [max_battles]
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from env.game_interface import sts


def check_observation_surface(bc):
    """Touch the tier-2 observation bindings and sanity-check them."""
    p = bc.player
    assert 0 < p.max_hp and 0 <= p.cur_hp <= p.max_hp
    assert p.get_status(sts.PlayerStatus.STRENGTH) == p.strength
    assert isinstance(p.has_relic(sts.RelicId.BURNING_BLOOD), bool)
    _ = (p.block, p.energy, p.energy_per_turn, p.dexterity, p.focus,
         p.stance, p.cards_played_this_turn)

    assert len(bc.monsters) == bc.monsters.monster_count
    for monster in bc.monsters:
        assert monster.max_hp > 0
        assert isinstance(monster.name, str) and monster.name
        dmg = monster.get_move_base_damage(bc)
        _ = (monster.id, monster.block, monster.move_id, monster.is_targetable,
             monster.get_status(sts.MonsterStatus.VULNERABLE),
             dmg.damage, dmg.attack_count)

    hand = bc.cards.hand
    assert len(hand) == bc.cards.cards_in_hand
    for c in hand:
        _ = (c.id, c.name, c.cost_for_turn, c.requires_target, c.upgraded)
    _ = (len(bc.cards.draw_pile), len(bc.cards.discard_pile),
         len(bc.cards.exhaust_pile), bc.potions)


def play_battle(gc, rng):
    bc = sts.BattleContext()
    bc.init(gc)
    check_observation_surface(bc)

    steps = 0
    while bc.outcome == sts.BattleOutcome.UNDECIDED:
        actions = bc.legal_actions()
        assert actions, (
            f"no legal actions but outcome UNDECIDED "
            f"(input_state={bc.input_state}, task={bc.card_select_info.task})"
        )
        for a in actions:
            assert a.is_valid(bc), f"legal_actions produced invalid action {a!r}"
            assert repr(a)
        assert len(set(actions)) == len(actions), "duplicate actions in legal set"

        a = rng.choice(actions)
        desc = a.describe(bc)
        a.execute(bc)
        steps += 1
        assert steps < 3000, f"battle seems stuck after {desc}"

    print(f"  floor {bc.floor_num} {bc.encounter}: {bc.outcome} "
          f"on turn {bc.turn} after {steps} actions, "
          f"hp {bc.player.cur_hp}/{bc.player.max_hp}")

    # copy-constructor sanity: a copy is independent of the original
    copy = sts.BattleContext(bc)
    assert copy.outcome == bc.outcome and copy.turn == bc.turn

    bc.exit_battle(gc)
    return bc.outcome


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    max_battles = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rng = random.Random(seed)
    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed, 0)

    battles = 0
    steps = 0
    while gc.outcome == sts.GameOutcome.UNDECIDED and battles < max_battles:
        if gc.screen_state == sts.ScreenState.BATTLE:
            play_battle(gc, rng)
            battles += 1
            continue

        actions = sts.GameAction.get_all_actions_in_state(gc)
        if not actions:
            # the engine punts on a few event screens (e.g. MATCH_AND_KEEP)
            print(f"no game actions on screen {gc.screen_state}; stopping early")
            break
        a = rng.choice(actions)
        assert a.is_valid(gc)
        a.execute(gc)
        steps += 1
        assert steps < 2000, "run seems stuck"

    assert battles >= 1, "random walk never reached a battle"
    print(f"done: outcome={gc.outcome} floor={gc.floor_num} battles={battles} "
          f"hp={gc.cur_hp}/{gc.max_hp} gold={gc.gold} "
          f"screen={gc.screen_state}")


if __name__ == "__main__":
    main()
