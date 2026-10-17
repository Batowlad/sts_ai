"""LLM-as-policy wrapper. TODO."""
import sys
from pathlib import Path

# Run this file directly and sys.path[0] is its own directory, so the `env.` /
# `agent.` package imports below would not resolve. Same shim as env/game_interface.py.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from env.game_interface import GameInterface
from env.state_encoder import encode_state
import torch
import json

from vllm import LLM, SamplingParams
from vllm.inputs import TokensPrompt

from agent.prompts import SYSTEM_PROMPT

_DUMP_PATH = _REPO_ROOT / "data" / "state_dump.jsonl"

class Policy:
    def __init__(self, cfg):
        self.cfg = cfg
        self.system_prompt = SYSTEM_PROMPT
        self.model = LLM(model=self.cfg.policy.model,
                   dtype=torch.bfloat16,
                   trust_remote_code=True,
#                  quantization="bitsandbytes" - for now commented out, not sure if it will be necessary tbh
                    )
        self.tokenizer = self.model.get_tokenizer()
        self.sampling_params = SamplingParams(temperature=self.cfg.policy.temperature, top_p=self.cfg.policy.top_p, max_tokens=self.cfg.policy.max_tokens, logprobs=0)


    def tokenize_state(self, state: str) -> list[int]:
        return self.tokenizer.apply_chat_template(
            [{"role": "system", "content": self.system_prompt},
            {"role": "user", "content": state}],
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
        )["input_ids"]


    def dump_state(self, state: str, **meta) -> list[int]:
        _DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_DUMP_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"state": state, "tokens": len(self.tokenize_state(state)), **meta}, ensure_ascii=False) + "\n")

    def act(self, state_text: str, legal_actions):
        model_inputs = self.tokenize_state(state_text + "\n" + legal_actions)

        return self.model.generate(TokensPrompt(prompt_token_ids=model_inputs), self.sampling_params)[0].outputs[0]

if __name__ == "__main__":
    import argparse
    from configs.config import load_config
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None,
                        help="path to a YAML config (default: configs/default.yaml)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    policy = Policy(cfg)
    gi = GameInterface()
    print(policy.act(encode_state(gi), gi.legal_actions()))