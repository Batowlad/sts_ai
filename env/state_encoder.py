"""Game state -> text. TODO."""

from game_interface import sts

def encode_state(gi) -> str:
        cur_screen = gi.gc.screen_state
        cur_hp = gi.gc.cur_hp
        max_hp = gi.gc.max_hp
        gold = gi.gc.gold
        potion_count = gi.gc.potion_count
        potion_capacity = gi.gc.potion_capacity

        map_x = gi.gc.cur_map_node_x
        map_y = gi.gc.cur_map_node_y

        deck = gi.view_deck()

        # BATTLE LIVE VIEW
        player_view = gi.bc.player
        monsters_view = gi.bc.monsters
        cards_view = gi.bc.cards

        if gi.gc.screen_state == sts.ScreenState.BATTLE:
            return (f"{player_view}, Monsters: {monsters_view}, Cards: {cards_view}, Deck: {deck}\n"
                    f"Status effects:\n{gi.view_statuses()}") # VERY VERY LIKELY TO BE EDITED
        elif gi.gc.screen_state == sts.ScreenState.MAP_SCREEN:
            if map_y == -1:
                 return f"Position: not yet on the map (choose a starting node), HP: {cur_hp}/{max_hp}, Gold amount: {gold}"
            else:
                return f"{gi.view_map()}\nCurrent map node: ({map_x}, {map_y}), HP: {cur_hp}/{max_hp}, Gold amount: {gold}"
        elif gi.gc.screen_state == sts.ScreenState.EVENT_SCREEN:
            return f"HP: {cur_hp}/{max_hp}, Gold amount: {gold}, Deck: {deck}"
        elif gi.gc.screen_state == sts.ScreenState.REST_ROOM:
            return f"HP: {cur_hp}/{max_hp}, Deck: {deck}"
        elif gi.gc.screen_state == sts.ScreenState.CARD_SELECT:
            return f"Deck: {deck}"
        elif gi.gc.screen_state == sts.ScreenState.SHOP_ROOM:
            return f"Gold amount: {gold}, potion slots: {potion_count}/{potion_capacity}"
        elif gi.gc.screen_state == sts.ScreenState.BOSS_RELIC_REWARDS:
            return (f"Deck: {deck}, Gold amount: {gold}\n"
                    f"{gi.view_relics()}")
        elif gi.gc.screen_state == sts.ScreenState.REWARDS:
            return (f"Deck: {deck}, Gold amount: {gold}\n"
                    f"{gi.view_relics()}\n{gi.view_potions()}")