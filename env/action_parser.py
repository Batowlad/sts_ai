"""Model text -> legal game action."""

import ast
from functools import cache
from pathlib import Path

from game_interface import sts

# Dispatched by hand below because they need arguments parsed out of the text,
# so they're deliberately kept out of the no-arg table get_funcs() builds.
SPECIAL_FUNCS = ("step", "card_describe")

# The model has to actually be asking about a card before a bare word is read as
# one: 31 card ids are ordinary English (DOUBT, SAFETY, RAGE, BLIND, TRIP...), so
# an ungated search turns "I'm in doubt about this" into a card lookup.
DESCRIBE_TRIGGERS = frozenset({
    "describe", "description", "explain", "what", "what's", "whats",
    "tell", "info", "card",
})

# Stripped off both ends of every word, since the model writes prose: 'bash?'
# has to still match BASH. '+' is left alone -- it means "the upgraded text".
PUNCTUATION = ".,!?;:\"'()[]"


@cache
def get_funcs():
    """Names of the GameInterface methods parse_action can call with no arguments."""
    # Relative to this file, not the cwd, so it works whatever dir you launch from.
    source = Path(__file__).with_name("game_interface.py")
    tree = ast.parse(source.read_text())

    funcs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_") or item.name in SPECIAL_FUNCS:
                        continue
                    # Called with no arguments, so anything that needs more
                    # than self would blow up.
                    if len(item.args.posonlyargs) + len(item.args.args) > 1:
                        continue
                    funcs.append(item.name)

    funcs.append("encode_state")

    return funcs


@cache
def get_func_words():
    """{word: method name} for every single word that can name a method on its own.

    Both the whole name and each underscore-separated part, so 'view_map',
    'view map' and 'see the map' all reach view_map. A part shared by several
    methods ('view') names none of them and is dropped, which is what lets the
    unambiguous half of 'view deck' decide instead of whichever word came first.
    """
    claims = {}
    for func in get_funcs():
        for key in (func, *func.split("_")):
            claims.setdefault(key, set()).add(func)
    return {key: funcs.pop() for key, funcs in claims.items() if len(funcs) == 1}


@cache
def get_card_ids():
    """{'BASH': CardId.BASH, ...} so words in the text can name a card."""
    return {name: cid for name, cid in sts.CardId.__members__.items() if name != "INVALID"}


@cache
def _max_card_words():
    return max(name.count("_") for name in get_card_ids()) + 1


def _find_card(words):
    """(CardId, upgraded) for the longest run of words naming a card, else None.

    Card ids are multi-word ('all for one' -> ALL_FOR_ONE), so the words have to be
    rejoined into a key -- a substring test can't do that, it can only check a key
    you already built. Longest run first, because 13 ids end in STRIKE and
    'wild strike' must not settle for plain STRIKE. Runs longer than the longest
    card id can't match, so capping the size keeps this linear in sentence length.
    """
    cards = get_card_ids()
    for size in range(min(len(words), _max_card_words()), 0, -1):
        for i in range(len(words) - size + 1):
            gram = "_".join(words[i:i + size])
            # A trailing '+' asks for the upgraded text.
            key = gram.rstrip("+").upper()
            if key in cards:
                return cards[key], gram.endswith("+")
    return None


def parse_action(text: str, gi, encode_state):
    words = [w for w in (w.strip(PUNCTUATION) for w in text.lower().split()) if w]

    # No trigger word means no card lookup, however card-like a word looks. If the
    # trigger is there but names nothing, fall through -- 'describe the map' is
    # still a perfectly good view_map.
    if not DESCRIBE_TRIGGERS.isdisjoint(words):
        found = _find_card(words)
        if found:
            return gi.card_describe(*found)

    func_words = get_func_words()
    for word in words:
        func = func_words.get(word)
        if func:
            # encode_state is a module-level function, not a GameInterface method.
            return encode_state(gi) if func == "encode_state" else getattr(gi, func)()

    # A bare number is an index into legal_actions().
    for word in words:
        if word.isdigit():
            return gi.step(int(word))

    raise ValueError(f"no action could be parsed out of {text!r}")


if __name__ == "__main__":
    from game_interface import GameInterface
    from state_encoder import encode_state

    gi = GameInterface()
    for probe in ("describe bash", "what's bash+?", "tell me about wild strike",
                  "I'm in doubt about this, show me the map", "state", "2"):
        print(f"{probe!r} -> {parse_action(probe, gi, encode_state)}")
