from game_interface import GameInterface
from state_encoder import encode_state
from action_parser import parse_action

game_interface = GameInterface()

# print(game_interface.view_map()) #view map at the beggining

game_interface.step(2) #starting choice
game_interface.step(0) #choose room

print(game_interface.view_map()) #view map at monster room
# print(game_interface.gc.cur_map_node_x)

game_interface.step(1) #play strike
game_interface.step(2) #play strike
game_interface.step(2) #play strike
game_interface.step(0) #end turn
game_interface.step(0) #play bash
game_interface.step(0) #play strike
game_interface.step(0) #end turn
game_interface.step(0) #play strike
game_interface.step(2) #play strike
game_interface.step(0) #collect rewards
game_interface.step(0) #collect rewards
game_interface.step(0) #collect rewards
game_interface.step(0) #collect rewards
game_interface.step(1) #go to shop

print(game_interface.view_map()) #view map at shop room
# print(game_interface.gc.cur_map_node_x)

game_interface.step(14)
game_interface.step(0)

print(game_interface.view_map()) #view map at shop room
# print(game_interface.gc.cur_map_node_x)