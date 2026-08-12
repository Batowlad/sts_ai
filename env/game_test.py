from game_interface import GameInterface
from state_encoder import encode_state
from action_parser import parse_action

game_interface = GameInterface()

input: str
while input != "exit":
    input = input("Enter: ")
    try:
        print(parse_action(input, game_interface, encode_state))
    except:
        print("Wrong input")