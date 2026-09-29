"""Game state -> text.

Now a two-step pipeline rather than one pile of f-strings: `observe.build_observation`
copies the engine into a typed `Observation`, and `render.render` turns that into the
text the policy reads. Anything that wants the *structure* (reward shaping, rollout
logging, eval metrics) should call `GameInterface.observe()` and skip the text.
"""

from observe import build_observation
from render import render

def encode_state(gi, *, reveal_draw_pile: bool = False, **render_opts) -> str:
    """`render_opts` are render()'s describe/map switches (describe_hand, describe_deck,
    route_summary, ascii_map), passed straight through."""
    state = render(build_observation(gi), reveal_draw_pile=reveal_draw_pile, **render_opts)
    return state