"""Game state -> text.

Now a two-step pipeline rather than one pile of f-strings: `observe.build_observation`
copies the engine into a typed `Observation`, and `render.render` turns that into the
text the policy reads. Anything that wants the *structure* (reward shaping, rollout
logging, eval metrics) should call `GameInterface.observe()` and skip the text.
"""

from observe import build_observation
from render import render

from transformers import AutoTokenizer
from yaml import SafeDumper, dump, safe_load
import functools

def encode_state(gi, *, reveal_draw_pile: bool = False) -> str:
    """The state text the policy reads.

    Still callable as `encode_state(gi)`, which is the form `env/action_parser.py` and
    the test harnesses pass around. `reveal_draw_pile` opts into showing the draw pile's
    real order - hidden information, so it is off unless you are debugging.
    """
    state = render(build_observation(gi), reveal_draw_pile=reveal_draw_pile)

    tokens = encoding_tokenizer(state)
    encoding_dump(state, tokens)

    return state

@functools.cache
def encoding_tokenizer(input):
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
    tokens = tokenizer.apply_chat_template(
        [{"role": "user", "content": input}],
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
    )

    return tokens["input_ids"]


class _StateDumper(SafeDumper):
    """Plain YAML only - raises on objects like tensors instead of pickling them."""


def _represent_str(dumper, text):
    # Multi-line text as a `|` block, so the dump reads like the rendered state.
    style = "|" if "\n" in text else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style=style)


_StateDumper.add_representer(str, _represent_str)


def encoding_dump(_input, _tokens):
    try:
        with open("data/state_dump.yaml", "r") as file:
            data = safe_load(file)
            data["input"].append(_input)
            data["tokens"].append(_tokens)
    except:
        data = {"input": [_input], "tokens": [_tokens]}


    with open("data/state_dump.yaml", "w") as file:
        dump(data, file, Dumper=_StateDumper, sort_keys=False, default_flow_style=None, width=100)
    