"""LLM-as-policy wrapper. TODO."""
from env.game_interface import GameInterface

class Policy:
    def act(self, state_text: str, legal_actions):
        raise NotImplementedError