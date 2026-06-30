"""Wraps the sts_lightspeed `slaythespire` pybind module.

Centralizes the import shim (build dir on sys.path + mingw DLL dir) so the rest
of the project can just `from env.game_interface import sts`.
"""
import os
import sys
from pathlib import Path

# Auto-detected relative to this repo, so a fresh clone works on any machine /
# any path with no edits. Override with the env vars only if your layout differs.
_REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = os.environ.get(
    "STS_BUILD_DIR", str(_REPO_ROOT / "sts_lightspeed" / "cmake-build-mingw")
)
# Only needed on Windows when the interpreter is NOT MSYS2's mingw64 python
# (with that one, the mingw DLLs sit next to python.exe and resolve for free).
MINGW_BIN = os.environ.get("STS_MINGW_BIN", r"C:\msys64\mingw64\bin")

if BUILD_DIR not in sys.path:
    sys.path.insert(0, BUILD_DIR)
if hasattr(os, "add_dll_directory") and os.path.isdir(MINGW_BIN):
    os.add_dll_directory(MINGW_BIN)

import slaythespire as sts  # noqa: E402


def new_game(character=None, seed: int = 42, ascension: int = 0):
    """Create a fresh GameContext (defaults to Ironclad)."""
    if character is None:
        character = sts.CharacterClass.IRONCLAD
    return sts.GameContext(character, seed, ascension)

# TODO: GameInterface class — step(), legal_actions(), reset(), run-combat-via-Agent, etc.

class GameInterface:
    def __init__(self):
        self.game_context = new_game()

    def step(self):
        print(1)

    def legal_actions(self):
        print(self.game_context)


game_interface = GameInterface()
game_interface.legal_actions()