"""Model text -> legal game action."""

import ast
from functools import cache
from pathlib import Path

from game_interface import sts
from game_data.card_data.card_text import CARD_DATA
from game_data.potion_data.potion_text import POTION_DATA
from game_data.relic_data.relic_text import RELIC_DATA
from game_data.status_data.status_text import MONSTER_STATUS_DATA, PLAYER_STATUS_DATA

# Dispatched by hand below because they need arguments parsed out of the text,
# so they're deliberately kept out of the no-arg table get_funcs() builds.
SPECIAL_FUNCS = (
    "step", "card_describe", "relic_describe", "potion_describe", "status_describe",
)

# Words that mean "the status, not the card that grants it". Every Ironclad power
# applies a status of the same name -- 48 ids collide, BARRICADE through
# WRAITH_FORM -- and the card is the more common question, so cards win by
# default; one of these words moves statuses to the front instead.
STATUS_WORDS = frozenset({
    "status", "statuses", "buff", "buffs", "debuff", "debuffs", "effect", "effects",
})

# Words that mean an enemy's copy of a status rather than yours. Both status enums
# carry WEAK, STRENGTH, THORNS... with the text written from opposite sides, and
# describe_status reads it as yours unless told otherwise.
MONSTER_WORDS = frozenset({
    "enemy", "enemys", "enemies", "monster", "monsters", "their", "theirs", "its",
})

# The model has to actually be asking about something before a bare word is read
# as a name: 31 card ids, 38 relic ids and 72 status ids are ordinary English
# (DOUBT, SAFETY, RAGE, ANCHOR, SHOVEL, WEAK...), so an ungated search turns
# "I'm in doubt about this" into a card lookup.
# Matched against already-normalized words, so no apostrophes here: "what's"
# reaches this set as 'whats'.
DESCRIBE_TRIGGERS = frozenset({
    "describe", "description", "explain", "what", "whats",
    "tell", "info", "card", "relic", "potion",
}) | STATUS_WORDS

# {kind: (id enums, display-name data)} for everything _find can name. `kind` is
# also the method prefix: 'relic' -> GameInterface.relic_describe. Iteration order
# is the order parse_action tries them in, so statuses go last -- see STATUS_WORDS.
# Cards, relics and potions share no id or display name at all, so their order
# only settles a tie a future one of them might introduce; statuses collide with
# 48 cards and with the Pen Nib relic, which is what the ordering is really for.
# Statuses take two enums because the same id lives in both, written from the
# player's side and the monster's; which one is meant is a MONSTER_WORDS question
# rather than an enum one, so _lookup resolves to id strings and lets
# describe_status pick the side.
_POOLS = {
    "card": ((sts.CardId,), CARD_DATA),
    "relic": ((sts.RelicId,), RELIC_DATA),
    "potion": ((sts.Potion,), POTION_DATA),
    "status": ((sts.PlayerStatus, sts.MonsterStatus),
               {**PLAYER_STATUS_DATA, **MONSTER_STATUS_DATA}),
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
    """({'BASH': 'BASH', 'STRIKE': 'STRIKE_RED', ...}, longest id in words) for one pool.

    Keyed by enum member name *and* by display name, because the two disagree:
    the Ironclad basics are STRIKE_RED/DEFEND_RED, so a plain 'strike' -- the
    most common card in the game -- would otherwise name nothing at all. Relics
    need it for the three ids that spell out punctuation the display name only
    hyphenates: 'Du-Vu Doll' normalizes to DUVU_DOLL, not DU_VU_DOLL.

    Display names come from game_data, and that's what keeps them unambiguous:
    STRIKE_BLUE/GREEN/PURPLE are all called 'Strike' too, but they're other
    classes and CARD_DATA is scoped to the Ironclad pool. A member name always
    wins over an alias, so an alias can never shadow a real id.

    Values are id strings, not enum members: every describe_* in game_data accepts
    a plain id, and a status id belongs to no single enum to be a member of.

    The enums are the wider side -- they carry every class's relics, potions and
    statuses, not just ours -- and the describe_* helpers name an out-of-scope id
    rather than raising, so those stay findable with no text attached.
    """
    enums, data = _POOLS[kind]
    ids = {n for enum in enums for n in enum.__members__ if n not in _NON_IDS}
    lookup = {n: n for n in ids}
    for name, entry in data.items():
        if name not in ids:                  # data for something this build lacks
            continue
        lookup.setdefault(_display_key(entry["name"]), name)
    return lookup, max(name.count("_") for name in lookup) + 1


def _find(words, kind):
    """(id, upgraded) for the longest run of words naming one, else None.

    Ids are multi-word ('all for one' -> ALL_FOR_ONE), so the words have to be
    rejoined into a key -- a substring test can't do that, it can only check a key
    you already built. Longest run first, because 13 card ids end in STRIKE and
    'wild strike' must not settle for plain STRIKE, the same way 'red skull' must
    not settle for SKULL. Runs longer than the longest id can't match, so capping
    the size keeps this linear in sentence length.

    `upgraded` only means anything for cards; relics, potions and statuses have no
    upgrade dimension and their callers drop it.
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


def _stack_count(words):
    """The bare number in 'describe vulnerable 2', which spells the text's X out.

    None when there isn't one, which describes the status generically. Only statuses
    read it -- for every other pool the number is left to the step() fallback, which
    never sees it anyway once a name has matched.
    """
    return next((int(w) for w in words if w.isdigit()), None)


def _owner(words):
    """'MONSTER' when the text asks about an enemy's status, else None for yours.

    None rather than 'PLAYER' so describe_status keeps its own fallback for the ids
    only monsters have (Curl Up, Mode Shift, ...).
    """
    return "MONSTER" if not MONSTER_WORDS.isdisjoint(words) else None


def parse_action(text: str, gi, encode_state):
    words = [w for w in (_normalize(w) for w in text.lower().split()) if w]

    # No trigger word means no name lookup, however card-like a word looks. If the
    # trigger is there but names nothing, fall through -- 'describe the map' is
    # still a perfectly good view_map, and 'describe my relics' a view_relics
    # (the plural is nobody's id, so it reaches the func words below).
    if not DESCRIBE_TRIGGERS.isdisjoint(words):
        kinds = list(_POOLS)
        if not STATUS_WORDS.isdisjoint(words):
            kinds.remove("status")
            kinds.insert(0, "status")
        for kind in kinds:
            found = _find(words, kind)
            if not found:
                continue
            value, upgraded = found
            if kind == "card":
                return gi.card_describe(value, upgraded)
            if kind == "status":
                return gi.status_describe(value, _stack_count(words), _owner(words))
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