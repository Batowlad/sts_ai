from game_interface import GameInterface
from state_encoder import encode_state
from action_parser import parse_action

game_interface = GameInterface()

user_input = None
while user_input != "exit":
    user_input = input("Enter: ")
    try:
        print(parse_action(user_input, game_interface, encode_state))
    except:
        print("Wrong input")