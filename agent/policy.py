"""LLM-as-policy wrapper. TODO."""
from env.game_interface import GameInterface
from env.state_encoder import encode_state, tokenize_state, _tokenizer
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
import torch

class Policy:
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