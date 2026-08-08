"""Model text -> legal game action. TODO."""

import ast
from functools import cache

@cache
def get_funcs():
    with open("env/game_interface.py") as f:
        tree = ast.parse(f.read())

    funcs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs.append(item.name)

    funcs.append("encode_state")

    return funcs

from game_interface import GameInterface
# from state_encoder import encode_state


def parse_action(text: str, encode_state, gi):
    print(get_funcs())
    text_list = text.split()
    for func in get_funcs():
        for word in text_list:
            if word in func:
                if func == "encode_state":
                    return encode_state(gi) #print for debug
                else:
                    return getattr(GameInterface, func)()

# parse_action("encode") #debug
