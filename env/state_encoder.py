"""Game state -> text.

Now a two-step pipeline rather than one pile of f-strings: `observe.build_observation`
copies the engine into a typed `Observation`, and `render.render` turns that into the
text the policy reads. Anything that wants the *structure* (reward shaping, rollout
logging, eval metrics) should call `GameInterface.observe()` and skip the text.
"""

from observe import build_observation
from render import render


def encode_state(gi, *, reveal_draw_pile: bool = False) -> str:
    """The state text the policy reads.

    Still callable as `encode_state(gi)`, which is the form `env/action_parser.py` and
    the test harnesses pass around. `reveal_draw_pile` opts into showing the draw pile's
    real order - hidden information, so it is off unless you are debugging.
    """
    return render(build_observation(gi), reveal_draw_pile=reveal_draw_pile)
