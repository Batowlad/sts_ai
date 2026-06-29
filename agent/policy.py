"""LLM-as-policy wrapper. TODO."""


class Policy:
    def act(self, state_text: str, legal_actions):
        raise NotImplementedError
