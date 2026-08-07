from game_interface import GameInterface
from state_encoder import encode_state

game_interface = GameInterface()
print(game_interface.view_map())
print(f"Legal actions: {game_interface.legal_actions()}")
game_interface.step(2) #starting bs choice
print(f"Legal actions: {game_interface.legal_actions()}")
# gi.step(1)
# print(f"Legal actions{gi.legal_actions()}")

print(game_interface.describe_card("BASH")) # DESCRIBING A CARD

print(encode_state(game_interface))# STATE AT MAP SCREEN

print(game_interface.gc.screen_state) # STATE OF SCREEN

game_interface.step(2) #starting bs choice

print(f"Legal actions: {game_interface.legal_actions()}")
print(game_interface.gc.screen_state) # STATE OF SCREEN
game_interface.bc.init(game_interface.gc)
game_interface.bc_initiated == True
print(encode_state(game_interface))# STATE AT BATTLE SCREEN