"""Model text -> legal game action. TODO."""

import ast

game_interface = "env/game_interface.py"

with open(game_interface, "r") as file:
    tree = ast.parse(file.read())

functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
print(functions)

def parse_action(text: str, legal_actions):
    raise NotImplementedError
