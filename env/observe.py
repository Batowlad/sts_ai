"""Engine objects -> typed snapshots.

The only module that knows both sides: it imports `game_interface` (for `sts` and the
naming/describe helpers) and `game_types` (for the dataclasses). `game_interface` only
reaches back in here lazily, from inside its methods, so the import graph stays acyclic.

    build_action_options(gi)   # tuple[ActionOption, ...] for the current screen
    build_observation(gi)      # Observation for the current screen

Both are pure reads: they copy out of the live C++ views and never step the engine.
"""
from __future__ import annotations

from game_interface import (
    TARGETED_POTIONS,
    _active_statuses,
    _card_name,
    _card_select_pile,
    _enum_name,
    _monster_name,
    _potion_name,
    _relic_name,
    _tail,
    describe,
    describe_battle,
    sts,
)
from game_types import (
    ActionKind,
    ActionOption,
    CardView,
    CombatView,
    EventView,
    MapChoice,
    MapView,
    MonsterView,
    Observation,
    PlayerView,
    PotionView,
    RelicView,
    RewardsView,
    RoomRange,
    ShopEntry,
    ShopView,
    StatusView,
)
from game_data.potion_data import potion_text

# Screens whose actions name nothing of their own: idx1 is just the option number.
_SCREEN_KINDS = {
    sts.ScreenState.EVENT_SCREEN: ActionKind.EVENT_OPTION,
    sts.ScreenState.REST_ROOM: ActionKind.REST_OPTION,
    sts.ScreenState.TREASURE_ROOM: ActionKind.TREASURE_OPTION,
    sts.ScreenState.MAP_SCREEN: ActionKind.MAP_MOVE,
    sts.ScreenState.CARD_SELECT: ActionKind.DECK_SELECT,
}

# REWARDS and SHOP_ROOM share one encoding: rewards_action_type picks which list idx1
# indexes (in gc.rewards_container or gc.shop), and which id field names the pick.
_POOLS = {
    sts.RewardsActionType.CARD: ("cards", "card_id"),
    sts.RewardsActionType.RELIC: ("relics", "relic_id"),
    sts.RewardsActionType.POTION: ("potions", "potion_id"),
}


def _id_of(obj) -> str | None:
    """Any engine id-ish object -> its id string ('BASH'); None stays None.

    Three shapes reach here: a wrapper with `.id` (Card, CardInstance, Relic), a bare
    enum with `.name` (CardId, RelicId, Potion), and an already-plain string.
    """
    if obj is None:
        return None
    inner = getattr(obj, "id", obj)
    return str(getattr(inner, "name", inner)).upper()


def _at(seq, i):
    """seq[i], or None for an index outside it - the describers guard engine indices
    the same way."""
    return seq[i] if 0 <= i < len(seq) else None


# ---------------------------------------------------------------- element views


def _card_view(card, *, detailed: bool = False) -> CardView:
    """A deck `Card`, a combat `CardInstance` or a bare `CardId` -> CardView.

    Every field is a pybind property read, and those reads are most of what a snapshot
    costs. So the playability fields are only read with `detailed=True` - for the hand
    and card-select offers, where the policy is choosing - and pile or deck cards get
    identity only. The name is built from the id string, so `.id` and `.upgraded` are
    read once rather than again inside `_card_name`.
    """
    cid = _id_of(card)
    upgraded = bool(getattr(card, "upgraded", False))
    extra = {}
    if detailed:
        extra = dict(
            cost=getattr(card, "cost_for_turn", None),
            card_type=_tail(getattr(card, "type", None)),
            requires_target=bool(getattr(card, "requires_target", False)),
            exhausts=bool(getattr(card, "does_exhaust", False)),
            ethereal=bool(getattr(card, "is_ethereal", False)),
        )
    return CardView(id=cid, name=_card_name(cid, upgraded), upgraded=upgraded, **extra)


def _relic_view(relic) -> RelicView:
    rid = _id_of(relic)
    return RelicView(id=rid, name=_relic_name(rid))


def _potion_view(potion, slot: int = -1) -> PotionView:
    pid = _id_of(potion)
    empty = potion_text.is_empty(pid)
    return PotionView(
        id=pid,
        name="(empty slot)" if empty else _potion_name(pid),
        slot=slot,
        is_empty=empty,
    )


def _status_views(holder, enum_cls, owner: str) -> tuple[StatusView, ...]:
    return tuple(
        StatusView(id=_tail(status), amount=amount, owner=owner)
        for status, amount in _active_statuses(holder, enum_cls)
    )


# ---------------------------------------------------------------- action options


def _combat_option(index: int, a, bc) -> ActionOption:
    """One `sts.Action` -> ActionOption. The label is `describe_battle`'s."""
    at = a.action_type
    common = dict(index=index, label=describe_battle(a, bc), screen="BATTLE", bits=a.bits)

    if at == sts.ActionType.END_TURN:
        return ActionOption(kind=ActionKind.END_TURN, **common)

    if at == sts.ActionType.CARD:
        card = _at(bc.cards.hand, a.source_idx)
        # Untargeted cards are enumerated with target_idx 0 too, so the card itself says
        # whether the target is real - the same rule describe_battle uses.
        targeted = card is not None and card.requires_target
        return ActionOption(
            kind=ActionKind.PLAY_CARD,
            card_id=_id_of(card),
            target_idx=a.target_idx if targeted else None,
            idx1=a.source_idx,
            **common,
        )

    if at == sts.ActionType.POTION:
        potion = _at(bc.potions, a.source_idx)
        discard = a.target_idx > 5          # a discard's -1 reads back as 8191 (13 bits)
        targeted = not discard and potion in TARGETED_POTIONS
        return ActionOption(
            kind=ActionKind.DISCARD_POTION if discard else ActionKind.USE_POTION,
            potion_id=_id_of(potion),
            target_idx=a.target_idx if targeted else None,
            idx1=a.source_idx,
            **common,
        )

    if at == sts.ActionType.SINGLE_CARD_SELECT:
        info = bc.card_select_info
        card = _at(_card_select_pile(info.task, bc, info), a.select_idx)
        return ActionOption(
            kind=ActionKind.SELECT_CARD, card_id=_id_of(card), idx1=a.select_idx, **common
        )

    if at == sts.ActionType.MULTI_CARD_SELECT:
        return ActionOption(
            kind=ActionKind.SELECT_CARDS, selected_idxs=tuple(a.selected_idxs), **common
        )

    return ActionOption(kind=ActionKind.UNKNOWN, **common)


def _container_option(a, gc, common: dict) -> ActionOption:
    """A REWARDS or SHOP_ROOM action (see `_POOLS`). Mirrors the indexing in
    `_describe_reward` / `_describe_shop`."""
    rt = a.rewards_action_type
    in_shop = gc.screen_state == sts.ScreenState.SHOP_ROOM

    # idx2 == 5 on a card reward is Singing Bowl: +2 max HP instead of a card.
    singing_bowl = not in_shop and rt == sts.RewardsActionType.CARD and a.idx2 == 5
    if rt == sts.RewardsActionType.SKIP or singing_bowl:
        return ActionOption(kind=ActionKind.SKIP, **common)
    if rt == sts.RewardsActionType.CARD_REMOVE:
        return ActionOption(kind=ActionKind.SHOP_REMOVE, **common)

    ids = {}
    if rt in _POOLS:            # GOLD and KEY name nothing; the label spells them out
        pool, field = _POOLS[rt]
        item = _at((gc.shop if in_shop else gc.rewards_container)[pool], a.idx1)
        if pool == "cards" and not in_shop and item is not None:
            item = _at(item, a.idx2)            # reward cards come in bundles
        ids[field] = _id_of(item)
    kind = ActionKind.SHOP_BUY if in_shop else ActionKind.TAKE_REWARD
    return ActionOption(kind=kind, **ids, **common)


# The room types a route summary counts, in the order it prints them. TREASURE is left
# out: every path crosses the one fixed treasure row, so it never tells routes apart.
_ROUTE_ROOMS = ("MONSTER", "ELITE", "EVENT", "REST", "SHOP")
_TOP_ROW = 14       # the row of rests before the boss


def _route_ranges(spire_map) -> dict[tuple[int, int], dict[str, tuple[int, int]]]:
    """{(x, y): {room: (fewest, most)}} over every path from that node to the top row.

    One pass from the top down: a node's range is its own room plus the min/max of its
    children's. Nodes with no edges up are off every path and are skipped, except on
    the top row, whose edges lead to the boss and aren't stored.
    """
    ranges: dict[tuple[int, int], dict[str, tuple[int, int]]] = {}
    for y in range(_TOP_ROW, -1, -1):
        for x in range(7):
            room = _tail(spire_map.get_room_type(x, y))
            if room in ("NONE", "INVALID"):
                continue
            own = {r: int(r == room) for r in _ROUTE_ROOMS}
            if y == _TOP_ROW:
                ranges[(x, y)] = {r: (n, n) for r, n in own.items()}
                continue
            children = [
                ranges[(x2, y + 1)] for x2 in range(7)
                if spire_map.has_edge(x, y, x2) and (x2, y + 1) in ranges
            ]
            if not children:
                continue
            ranges[(x, y)] = {
                r: (own[r] + min(c[r][0] for c in children),
                    own[r] + max(c[r][1] for c in children))
                for r in _ROUTE_ROOMS
            }
    return ranges


def _map_view(gi) -> MapView:
    """Where you are, and for each node you can move to, what the routes through it
    hold. The ASCII map rides along for debugging; `render` only prints it on request."""
    gc = gi.gc
    x, y = gc.cur_map_node_x, gc.cur_map_node_y
    spire_map = gi.map
    if spire_map is None or y >= _TOP_ROW:
        return MapView(x=x, y=y, ascii_map=gi.view_map())

    ranges = _route_ranges(spire_map)
    choices = []
    for x2 in range(7):
        # has_edge(-1, ...) asks whether the bottom-row node x2 starts a path.
        if not spire_map.has_edge(x, y, x2) or (x2, y + 1) not in ranges:
            continue
        ahead = tuple(
            RoomRange(room=r, min=lo, max=hi) for r, (lo, hi) in ranges[(x2, y + 1)].items()
        )
        room = _tail(spire_map.get_room_type(x2, y + 1))
        choices.append(MapChoice(x=x2, y=y + 1, room=room, ahead=ahead))
    return MapView(x=x, y=y, ascii_map=gi.view_map(), choices=tuple(choices))


def _game_option(index: int, a, gi) -> ActionOption:
    """One `sts.GameAction` -> ActionOption. The label is `describe`'s."""
    gc = gi.gc
    ss = gc.screen_state

    label = describe(a, gc)
    if ss == sts.ScreenState.MAP_SCREEN and not a.is_potion_action and gi.map is not None:
        # idx1 is the x of the node one row up; say what room it leads to.
        room = gi.map.get_room_type(a.idx1, gc.cur_map_node_y + 1)
        if _tail(room) not in ("NONE", "INVALID"):
            label += f" ({_enum_name(room)} Room)"

    common = dict(
        index=index, label=label, screen=_tail(ss), bits=a.bits, idx1=a.idx1, idx2=a.idx2
    )

    # Potions can be used on any screen, so they are checked first - the order the
    # engine's own decoding guide prescribes.
    if a.is_potion_action:
        return ActionOption(
            kind=ActionKind.DISCARD_POTION if a.is_potion_discard else ActionKind.USE_POTION,
            potion_id=_id_of(_at(gc.potions, a.idx1)),
            **common,
        )
    if ss in _SCREEN_KINDS:
        return ActionOption(kind=_SCREEN_KINDS[ss], **common)
    if ss == sts.ScreenState.BOSS_RELIC_REWARDS:
        if a.idx1 == 3:
            return ActionOption(kind=ActionKind.SKIP, **common)
        relic = _at(gc.boss_relics, a.idx1)
        return ActionOption(kind=ActionKind.BOSS_RELIC, relic_id=_id_of(relic), **common)
    if ss in (sts.ScreenState.REWARDS, sts.ScreenState.SHOP_ROOM):
        return _container_option(a, gc, common)
    return ActionOption(kind=ActionKind.UNKNOWN, **common)


def build_action_options(gi) -> tuple[ActionOption, ...]:
    """Every legal choice right now, numbered by position - the index `step()` takes."""
    if gi.gc.screen_state == sts.ScreenState.BATTLE:
        if not gi.bc_initiated:
            return ()
        actions = sts.get_legal_actions(gi.bc)
        return tuple(_combat_option(i, a, gi.bc) for i, a in enumerate(actions))

    actions = sts.GameAction.get_all_actions_in_state(gi.gc)
    return tuple(_game_option(i, a, gi) for i, a in enumerate(actions))


# ---------------------------------------------------------------- observation


def _monster_view(bc, idx, monster) -> MonsterView:
    attacking = bool(monster.is_attacking)
    damage = count = incoming = None
    if attacking:
        info = monster.get_move_base_damage(bc)
        damage, count = info.damage, info.attack_count
        incoming = monster.calculate_damage_to_player(bc, damage)
    return MonsterView(
        idx=idx,
        id=_tail(monster.id),
        name=_monster_name(bc, idx),
        cur_hp=monster.cur_hp,
        max_hp=monster.max_hp,
        block=monster.block,
        intent=_tail(monster.move_id),
        is_attacking=attacking,
        attack_damage=damage,
        attack_count=count,
        incoming_damage=incoming,
        is_dead_or_escaped=bool(monster.is_dead_or_escaped),
        statuses=_status_views(monster, sts.MonsterStatus, "MONSTER"),
    )


def _combat_view(bc) -> CombatView:
    p = bc.player
    cards = bc.cards

    select = {}
    if bc.input_state == sts.InputState.CARD_SELECT:
        info = bc.card_select_info
        select = dict(
            card_select_task=_tail(info.task),
            card_select_pick_count=info.pick_count,
            card_select_can_pick_zero=bool(info.can_pick_zero),
            card_select_cards=tuple(_card_view(c, detailed=True) for c in info.cards),
        )

    return CombatView(
        turn=bc.turn,
        encounter=_tail(bc.encounter),
        outcome=_tail(bc.outcome),
        input_state=_tail(bc.input_state),
        player=PlayerView(
            cur_hp=p.cur_hp,
            max_hp=p.max_hp,
            block=p.block,
            energy=p.energy,
            strength=p.strength,
            dexterity=p.dexterity,
            stance=_tail(p.stance),
            statuses=_status_views(p, sts.PlayerStatus, "PLAYER"),
        ),
        monsters=tuple(_monster_view(bc, i, m) for i, m in enumerate(bc.monsters)),
        hand=tuple(_card_view(c, detailed=True) for c in cards.hand),
        draw_pile=tuple(_card_view(c) for c in cards.draw_pile),
        discard_pile=tuple(_card_view(c) for c in cards.discard_pile),
        exhaust_pile=tuple(_card_view(c) for c in cards.exhaust_pile),
        **select,
    )


def _rewards_view(gc) -> RewardsView:
    r = gc.rewards_container
    return RewardsView(
        gold=tuple(r["gold"]),
        card_bundles=tuple(tuple(_card_view(c) for c in bundle) for bundle in r["cards"]),
        relics=tuple(_relic_view(x) for x in r["relics"]),
        potions=tuple(_potion_view(x) for x in r["potions"]),
        emerald_key=bool(r["emerald_key"]),
        sapphire_key=bool(r["sapphire_key"]),
    )


def _shop_view(gc) -> ShopView:
    """`gc.shop` -> ShopView. Each item row pairs with its price row by slot, and a price
    of -1 marks an empty slot."""
    s = gc.shop
    rows = {}
    for pool, namer in (("cards", _card_name), ("relics", _relic_name), ("potions", _potion_name)):
        prices = s[pool[:-1] + "_prices"]           # 'cards' -> 'card_prices'
        rows[pool] = tuple(
            ShopEntry(
                slot=slot,
                id=_id_of(item),
                name=namer(item),
                price=price,
                upgraded=bool(getattr(item, "upgraded", False)),
            )
            for slot, (item, price) in enumerate(zip(s[pool], prices))
            if price >= 0
        )
    return ShopView(**rows, remove_cost=s["remove_cost"])


def build_observation(gi) -> Observation:
    """A detached snapshot of the current decision point.

    Screen-specific blocks are only read on the screen that makes them meaningful -
    `rewards_container` and `shop` hold uninitialized garbage anywhere else.
    """
    gc = gi.gc
    ss = gc.screen_state
    in_combat = ss == sts.ScreenState.BATTLE and gi.bc_initiated
    # bc keeps its own copy of the belt and only writes it back on exit_battle, so
    # gc.potions goes stale mid-fight.
    belt = gi.bc.potions if in_combat else gc.potions
    keys = (("ruby", gc.red_key), ("emerald", gc.green_key), ("sapphire", gc.blue_key))

    common = dict(
        screen=_tail(ss),
        floor=gc.floor_num,
        act=gc.act,
        cur_hp=gc.cur_hp,
        max_hp=gc.max_hp,
        gold=gc.gold,
        outcome=_tail(gc.outcome),
        potion_count=gc.potion_count,
        potion_capacity=gc.potion_capacity,
        deck=tuple(_card_view(c) for c in gc.deck),
        relics=tuple(_relic_view(r) for r in gc.relics),
        potions=tuple(_potion_view(p, i) for i, p in enumerate(belt)),
        keys=tuple(name for name, held in keys if held),
    )

    if in_combat:
        return Observation(combat=_combat_view(gi.bc), **common)
    if ss == sts.ScreenState.MAP_SCREEN:
        return Observation(map_view=_map_view(gi), **common)
    if ss == sts.ScreenState.REWARDS:
        return Observation(rewards=_rewards_view(gc), **common)
    if ss == sts.ScreenState.SHOP_ROOM:
        return Observation(shop=_shop_view(gc), **common)
    if ss == sts.ScreenState.EVENT_SCREEN:
        event = EventView(name=gc.cur_event_name, event_data=gc.event_data)
        return Observation(event=event, **common)
    # TREASURE_ROOM, REST_ROOM, BOSS_RELIC_REWARDS, CARD_SELECT: the common fields.
    return Observation(**common)
