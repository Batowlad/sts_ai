"""Model text -> legal game action."""

import ast
from functools import cache
from pathlib import Path

from game_interface import sts
from game_data.card_data.card_text import CARD_DATA
from game_data.potion_data.potion_text import POTION_DATA
from game_data.relic_data.relic_text import RELIC_DATA

# Dispatched by hand below because they need arguments parsed out of the text,
# so they're deliberately kept out of the no-arg table get_funcs() builds.
SPECIAL_FUNCS = ("step", "card_describe", "relic_describe", "potion_describe")

# The model has to actually be asking about something before a bare word is read
# as a name: 31 card ids and 38 relic ids are ordinary English (DOUBT, SAFETY,
# RAGE, ANCHOR, LANTERN, SHOVEL...), so an ungated search turns "I'm in doubt
# about this" into a card lookup.
# Matched against already-normalized words, so no apostrophes here: "what's"
# reaches this set as 'whats'.
DESCRIBE_TRIGGERS = frozenset({
    "describe", "description", "explain", "what", "whats",
    "tell", "info", "card", "relic", "potion",
})

# {kind: (id enum, display-name data)} for everything _find can name. `kind` is
# also the method prefix: 'relic' -> GameInterface.relic_describe. Iteration
# order is the order parse_action tries them in -- no id or display name is
# shared across the three pools today, so it only settles a future tie.
_POOLS = {
    "card": (sts.CardId, CARD_DATA),
    "relic": (sts.RelicId, RELIC_DATA),
    "potion": (sts.Potion, POTION_DATA),
}

# Placeholder enum members that never name anything the model can ask about.
_NON_IDS = frozenset({"INVALID", "EMPTY_POTION_SLOT"})


def _normalize(word: str) -> str:
    """Drop every non-alphanumeric character, keeping a trailing '+'.

    The model writes prose, so 'bash?' has to still match BASH -- but stripping
    the *ends* isn't enough: punctuation shows up mid-word too, and 'j.a.x.' is
    JAX while "ascender's" is ASCENDERS. '+' survives because it means "the
    upgraded text"; a word that is nothing but punctuation normalizes to '' and
    parse_action drops it.
    """
    core = "".join(ch for ch in word if ch.isalnum())
    return core + "+" if core and word.endswith("+") else core


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


def _display_key(display: str) -> str:
    """'Bird-Faced Urn' -> 'BIRDFACED_URN'.

    Built exactly the way _find builds its lookup key, or it'd never match.
    """
    parts = [p for p in (_normalize(w) for w in display.lower().split()) if p]
    return "_".join(parts).upper()


@cache
def _lookup(kind):
    """({'BASH': CardId.BASH, ...}, longest id in words) for one pool.

    Keyed by enum member name *and* by display name, because the two disagree:
    the Ironclad basics are STRIKE_RED/DEFEND_RED, so a plain 'strike' -- the
    most common card in the game -- would otherwise name nothing at all. Relics
    need it for the three ids that spell out punctuation the display name only
    hyphenates: 'Du-Vu Doll' normalizes to DUVU_DOLL, not DU_VU_DOLL.

    Display names come from game_data, and that's what keeps them unambiguous:
    STRIKE_BLUE/GREEN/PURPLE are all called 'Strike' too, but they're other
    classes and CARD_DATA is scoped to the Ironclad pool. A member name always
    wins over an alias, so an alias can never shadow a real id.

    The enum is the wider of the two -- it carries every class's relics and
    potions, not just ours -- and describe_relic/describe_potion name an
    out-of-scope id rather than raising, so those stay findable with no text.
    """
    enum, data = _POOLS[kind]
    ids = {n: v for n, v in enum.__members__.items() if n not in _NON_IDS}
    lookup = dict(ids)
    for name, entry in data.items():
        value = ids.get(name)
        if value is None:                    # data for something this build lacks
            continue
        lookup.setdefault(_display_key(entry["name"]), value)
    return lookup, max(name.count("_") for name in lookup) + 1


def _find(words, kind):
    """(id, upgraded) for the longest run of words naming one, else None.

    Ids are multi-word ('all for one' -> ALL_FOR_ONE), so the words have to be
    rejoined into a key -- a substring test can't do that, it can only check a key
    you already built. Longest run first, because 13 card ids end in STRIKE and
    'wild strike' must not settle for plain STRIKE, the same way 'red skull' must
    not settle for SKULL. Runs longer than the longest id can't match, so capping
    the size keeps this linear in sentence length.

    `upgraded` only means anything for cards; relics and potions have no upgrade
    dimension and their caller drops it.
    """
    ids, max_size = _lookup(kind)
    for size in range(min(len(words), max_size), 0, -1):
        for i in range(len(words) - size + 1):
            gram = "_".join(words[i:i + size])
            # A trailing '+' asks for the upgraded text.
            key = gram.rstrip("+").upper()
            if key in ids:
                return ids[key], gram.endswith("+")
    return None


def parse_action(text: str, gi, encode_state):
    words = [w for w in (_normalize(w) for w in text.lower().split()) if w]

    # No trigger word means no name lookup, however card-like a word looks. If the
    # trigger is there but names nothing, fall through -- 'describe the map' is
    # still a perfectly good view_map, and 'describe my relics' a view_relics
    # (the plural is nobody's id, so it reaches the func words below).
    if not DESCRIBE_TRIGGERS.isdisjoint(words):
        for kind in _POOLS:
            found = _find(words, kind)
            if found:
                value, upgraded = found
                if kind == "card":
                    return gi.card_describe(value, upgraded)
                # Relics and potions have no upgrade dimension.
                return getattr(gi, f"{kind}_describe")(value)

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