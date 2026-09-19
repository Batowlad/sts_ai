from game_interface import GameInterface
from state_encoder import encode_state
from action_parser import parse_action, parse_structured_action

game_interface = GameInterface()

user_input = None
while user_input != "exit":
    user_input = input("Enter: ")
    try:
        # A '{' means the policy's own dialect, so one REPL exercises both paths.
        if "{" in user_input:
            result = parse_structured_action(user_input, game_interface)
        else:
            result = parse_action(user_input, game_interface, encode_state)
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        continue
    if result is not None:
        print(result)
