"""Snapshot -> text. The only place that decides what the policy actually reads.

Pure functions of `env/game_types` values: no engine import, no `game_interface`
import, so everything here is testable by hand-building an `Observation`.

Keeping this separate from extraction is what lets the snapshot capture *everything*
while the prompt shows only what a player could legitimately know - see
`reveal_draw_pile`, which is off by default because the draw pile's order is hidden
information and an agent trained on it learns a policy it cannot run.
"""
from __future__ import annotations

from collections import Counter

from game_data.card_data.card_text import describe_card
from game_data.potion_data.potion_text import describe_potion
from game_data.relic_data.relic_text import describe_relic
from game_data.status_data.status_text import describe_status

from game_types import ActionOption, Observation


def _counted(names) -> str:
    """['Strike', 'Strike', 'Bash'] -> '2x Strike, 1x Bash', first-seen order."""
    return ", ".join(f"{n}x {name}" for name, n in Counter(names).items()) or "empty"


def _glossary(header: str, descriptions) -> list[str]:
    """`header` plus one '- line' per distinct description, first-seen order; [] if none.

    Dedup is on the text itself, so a hand of Strike, Strike, Bash describes two cards
    - which is what keeps these legends inside the context budget.
    """
    lines = [f"- {d}" for d in dict.fromkeys(descriptions)]
    return [header, *lines] if lines else []


def _combat_section(combat, reveal_draw_pile: bool) -> list[str]:
    p = combat.player
    stance = f", stance {p.stance}" if p.stance not in (None, "NEUTRAL") else ""
    out = [
        f"Combat vs {combat.encounter} - turn {combat.turn}",
        f"You: {p.cur_hp}/{p.max_hp} HP, {p.block} block, {p.energy} energy{stance}",
    ]

    alive = [m for m in combat.monsters if not m.is_dead_or_escaped]
    for m in alive:
        line = f"  {m.name}: {m.cur_hp}/{m.max_hp} HP" + (f", {m.block} block" if m.block else "")
        if m.is_attacking and m.attack_damage is not None:
            dealt = m.attack_damage if m.incoming_damage is None else m.incoming_damage
            hits = f" x{m.attack_count}" if (m.attack_count or 1) > 1 else ""
            line += f" - intends to attack for {dealt}{hits}"
        elif m.intent:
            line += f" - intent: {m.intent}"
        out.append(line)

    out.append(f"Hand ({len(combat.hand)}): {', '.join(c.name for c in combat.hand) or 'empty'}")
    out.append(
        f"Draw {len(combat.draw_pile)} | Discard {len(combat.discard_pile)} "
        f"| Exhaust {len(combat.exhaust_pile)}"
    )
    if combat.draw_pile:
        if reveal_draw_pile:
            out.append(f"Draw pile (order): {', '.join(c.name for c in combat.draw_pile)}")
        else:
            # Contents without order: what a player can work out by counting, no more.
            out.append(f"Draw pile contents: {_counted(c.name for c in combat.draw_pile)}")
    if combat.discard_pile:
        out.append(f"Discard pile: {_counted(c.name for c in combat.discard_pile)}")

    if combat.card_select_task:
        zero = " (zero allowed)" if combat.card_select_can_pick_zero else ""
        out.append(
            f"Card select ({combat.card_select_task}): "
            f"pick {combat.card_select_pick_count}{zero}"
        )
        if combat.card_select_cards:
            out.append(f"Offered: {', '.join(c.name for c in combat.card_select_cards)}")

    out += _glossary("Cards in hand:", (describe_card(c.id, c.upgraded) for c in combat.hand))
    out.append("Status effects:")
    for name, statuses in [("You", p.statuses), *((m.name, m.statuses) for m in alive)]:
        described = (describe_status(s.id, s.amount, s.owner) for s in statuses)
        out += _glossary(f"{name}:", described) or [f"{name}: no status effects."]
    return out


def _rewards_section(rewards) -> list[str]:
    out = ["Rewards on offer:"]
    out += [f"- {g} gold" for g in rewards.gold]
    out += [
        f"- card choice {i}: {', '.join(c.name for c in bundle)}"
        for i, bundle in enumerate(rewards.card_bundles)
    ]
    out += [f"- relic: {describe_relic(r.id)}" for r in rewards.relics]
    out += [f"- potion: {describe_potion(p.id)}" for p in rewards.potions]
    keys = (("emerald", rewards.emerald_key), ("sapphire", rewards.sapphire_key))
    out += [f"- the {name} key" for name, offered in keys if offered]
    cards = (c for bundle in rewards.card_bundles for c in bundle)
    return out + _glossary("Card details:", (describe_card(c.id, c.upgraded) for c in cards))


def _shop_section(shop) -> list[str]:
    out = ["Shop stock:"]
    out += [f"- {describe_card(e.id, e.upgraded)} - {e.price} gold" for e in shop.cards]
    out += [f"- {describe_relic(e.id)} - {e.price} gold" for e in shop.relics]
    out += [f"- {describe_potion(e.id)} - {e.price} gold" for e in shop.potions]
    return out + [f"- card removal: {shop.remove_cost} gold"]


def render(obs: Observation, *, reveal_draw_pile: bool = False) -> str:
    """The state text the policy sees.

    Every screen gets the vitals line, then whichever blocks that screen makes
    meaningful - so a screen with nothing special still renders rather than vanishing.
    """
    held = [p for p in obs.potions if not p.is_empty]
    vitals = [
        f"Floor {obs.floor} (act {obs.act})",
        f"HP: {obs.cur_hp}/{obs.max_hp}",
        f"Gold: {obs.gold}",
        f"Potions: {len(held)}/{obs.potion_capacity}",
    ]
    if obs.keys:
        vitals.append(f"Keys: {', '.join(obs.keys)}")
    out = [f"Screen: {obs.screen}", " | ".join(vitals)]

    if obs.combat is not None:
        out += _combat_section(obs.combat, reveal_draw_pile)
    else:
        # Out of combat the deck is the decision; in combat the hand is, and the full
        # deck listing just crowds the context.
        out.append(f"Deck ({len(obs.deck)}): {_counted(c.name for c in obs.deck)}")

    if obs.map_view is not None:
        mv = obs.map_view
        if mv.ascii_map:
            out.append(mv.ascii_map)
        out.append(
            f"Map position: ({mv.x}, {mv.y})" if mv.y >= 0
            else "Map position: not yet on the map (choose a starting node)"
        )
    if obs.event is not None:
        out.append(f"Event: {obs.event.name}")
    if obs.rewards is not None:
        out += _rewards_section(obs.rewards)
    if obs.shop is not None:
        out += _shop_section(obs.shop)

    out += _glossary("Relics:", (describe_relic(r.id) for r in obs.relics))
    out += _glossary(
        f"Potions ({len(held)}/{obs.potion_capacity} slots full):",
        (describe_potion(p.id) for p in held),
    )
    return "\n".join(out)


def render_action_options(options: tuple[ActionOption, ...], screen: str = "") -> str:
    """The legal-action list as one prompt-ready line.

    Keeps the wording `env/action_parser.py` was written against: the model answers with
    the bare number, which `parse_action` reads as an index into this list.
    """
    if not options:
        return "No legal actions on this screen."
    listing = [f"{o.index}. {o.label}" for o in options]
    note = " (You can only select one card/relic)" if screen in ("REWARDS", "BOSS_RELIC_REWARDS") else ""
    return f"Enter a number of the action{note}: {listing}"
