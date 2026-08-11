"""Model text -> legal game action. TODO."""

import ast
from functools import cache
from pathlib import Path

@cache
def get_funcs():
    # Relative to this file, not the cwd, so it works whatever dir you launch from.
    source = Path(__file__).with_name("game_interface.py")
    tree = ast.parse(source.read_text())

    funcs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_"): 
                        continue
                    # parse_action calls these with no arguments, so anything
                    # that needs more than self would blow up. TODO: step() and
                    # describe_card() need their args parsed out of the text.
                    if len(item.args.posonlyargs) + len(item.args.args) > 1:
                        continue
                    funcs.append(item.name)

    funcs.append("encode_state")

    return funcs

from game_interface import GameInterface
# from state_encoder import encode_state


def parse_action(text: str, gi, encode_state):
    print(get_funcs())
    text_list = text.split()
    for func in get_funcs():
        for word in text_list:
            if word in func:
                if func == "encode_state":
                    return encode_state(gi) #print for debug
                else:
                    # Bind to the live instance — getattr on the class gives an
                    # unbound function that still wants self.
                    return getattr(gi, func)()

# parse_action("encode") #debug
