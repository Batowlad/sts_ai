"""Game state -> text.

Now a two-step pipeline rather than one pile of f-strings: `observe.build_observation`
copies the engine into a typed `Observation`, and `render.render` turns that into the
text the policy reads. Anything that wants the *structure* (reward shaping, rollout
logging, eval metrics) should call `GameInterface.observe()` and skip the text.
"""

import json
from pathlib import Path

from observe import build_observation
from render import render

import functools

def encode_state(gi, *, reveal_draw_pile: bool = False, **render_opts) -> str:
    """`render_opts` are render()'s describe/map switches (describe_hand, describe_deck,
    route_summary, ascii_map), passed straight through."""
    state = render(build_observation(gi), reveal_draw_pile=reveal_draw_pile, **render_opts)
    return state

@functools.cache
def _tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")


def tokenize_state(state: str) -> list[int]:
    return _tokenizer().apply_chat_template(
        [{"role": "user", "content": state}],
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
    )["input_ids"]


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DUMP_PATH = _REPO_ROOT / "data" / "state_dump.jsonl"



def dump_state(state: str, **meta) -> list[int]:
    _DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_DUMP_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"state": state, "tokens": len(tokenize_state(state)), **meta}, ensure_ascii=False) + "\n")