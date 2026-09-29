"""LLM-as-policy wrapper. TODO."""
from env.game_interface import GameInterface
from env.state_encoder import encode_state
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
import torch
import functools
from pathlib import Path
import json

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DUMP_PATH = _REPO_ROOT / "data" / "state_dump.jsonl"

class Policy:
    @functools.cache
    def _tokenizer():
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")


    def tokenize_state(self, state: str, system_prompt: str) -> list[int]:
        return _tokenizer().apply_chat_template(
            [{"role": "system", "content": system_prompt},
            {"role": "user", "content": state}],
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
        )["input_ids"]


    def dump_state(self, state: str, **meta) -> list[int]:
        _DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_DUMP_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"state": state, "tokens": len(tokenize_state(state)), **meta}, ensure_ascii=False) + "\n")

    @torch.inference_mode
    def act(self, state_text: str, legal_actions):
        quantization_config = BitsAndBytesConfig(load_in_4bit=True)
        model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct", device_map="auto", quantization_config=quantization_config)
        model_inputs = tokenize_state(state_text + "\n" + legal_actions).to(model.device)
        generated_ids = model.generate(**model_inputs)
        _tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

policy = Policy()
gi = GameInterface()
policy.act(encode_state(gi), gi.legal_actions())