from game_interface import GameInterface
from state_encoder import encode_state
from action_parser import parse_action

game_interface = GameInterface()
print(game_interface.view_map())
print(f"Legal actions: {game_interface.legal_actions()}")
game_interface.step(2) #starting bs choice
print(f"Legal actions: {game_interface.legal_actions()}")
# gi.step(1)
# print(f"Legal actions{gi.legal_actions()}")

print(game_interface.describe_card("BASH")) # DESCRIBING A CARD

print(encode_state(game_interface))# STATE AT MAP SCREEN
parse_action("I want to see the map", game_interface, encode_state) #parse view_map from string input
print(game_interface.gc.screen_state) # STATE OF SCREEN

print(parse_action("state", game_interface, encode_state)) #parse action test

game_interface.step(2) #Move into combat
print(f"Legal actions: {game_interface.legal_actions()}")
print(game_interface.gc.screen_state) # STATE OF SCREEN
print(encode_state(game_interface))# STATE AT BATTLE SCREEN

game_interface.step(1) #first action in combat
print(encode_state(game_interface))# STATE AFTER FIRST COMBAT ACTION
