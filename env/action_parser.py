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

    return funcs

def parse_action(text: str):
    print(get_funcs())

parse_action("")
