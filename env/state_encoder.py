"""Game state -> text. TODO."""

from game_interface import sts


def encode_state(gc, bc) -> str:
    if gc.screen_state == sts.ScreenState.BATTLE:
        print(1)
    else:
        return gc.__repr__()
