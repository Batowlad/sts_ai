"""The env package.

Modules in here import their siblings flat (`from game_types import ...`) because the
scripts in this directory are run directly, while callers outside it use the package
path (`from env.game_types import ...`). Python treats those as two different modules
and builds two of everything: two `ActionOption` classes, two `Observation` classes, and
every `isinstance()` across the boundary silently returns False.

Registering one module object under both names is what keeps that from happening. Only
`game_types` needs it — it is the one module whose *classes* are identity-sensitive, and
it is stdlib-only, so importing it here costs nothing. The rest export functions, where a
duplicate import is wasteful at worst.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Works in either direction: flat-first (a script run from inside env/) or package-first
# (`from env.game_interface import ...` from the repo root).
if "game_types" in sys.modules:
    sys.modules["env.game_types"] = sys.modules["game_types"]
else:
    from . import game_types as _game_types

    sys.modules["game_types"] = _game_types
