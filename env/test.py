from game_interface import GameInterface

gi = GameInterface()
print(gi.legal_actions())
print(gi.view_map())
gi.step(1)
print(gi.legal_actions())
gi.step(1)
print(gi.legal_actions())