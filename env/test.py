from game_interface import GameInterface

gi = GameInterface()
print(gi.view_map())
print(f"Legal actions{gi.legal_actions()}")
print(gi.encode_state())
gi.step(2) #starting bs choice
print(f"Legal actions{gi.legal_actions()}")
# gi.step(1)
# print(f"Legal actions{gi.legal_actions()}")
print(gi.encode_state())