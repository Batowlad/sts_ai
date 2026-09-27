"""LLM-as-policy wrapper. TODO."""
from env.game_interface import GameInterface
from env.state_encoder import encode_state

class Policy:
    def act(self, state_text: str, legal_actions):
        print(state_text)
        print(legal_actions)


policy = Policy()
gi = GameInterface()
policy.act(encode_state(gi), gi.legal_actions())