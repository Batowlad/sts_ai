"""Pydantic models for the generated `*_data.json` tables.

These files are a trust boundary: they are produced by the `build_*_data.py` scripts out
of a spreadsheet and the engine headers, then read on every import by the text modules.
Validating them once at load is cheap and turns a silent `KeyError` deep in a prompt
render into one clear message naming the offending entry.

This is the right place for pydantic. The per-step `Observation` and `ActionOption` in
`env/game_types.py` are plain dataclasses on purpose - they are built thousands of times
per rollout from data the C++ engine has already validated, so re-validating each field
would be pure overhead on the hottest path.

`extra="forbid"` is deliberate: these JSONs are generated, so an unexpected key means the
builder and the reader have drifted apart, which is exactly what we want to hear about.
`frozen=True` because the loaded tables are process-wide globals.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    text: str


class CardEntry(_Entry):
    type: str
    rarity: str
    color: str
    cost: str                        # '2', but also 'X' and 'Unplayable'
    cost_upgraded: str | None = None
    text_upgraded: str | None = None


class RelicEntry(_Entry):
    rarity: str
    character: str | None = None     # None for the shared pool


class PotionEntry(_Entry):
    rarity: str
    requires_target: bool


class StatusEntry(_Entry):
    owner: str                       # 'PLAYER' | 'MONSTER'
    kind: str                        # 'buff' | 'debuff' | ...
    stacks: bool                     # False for flag-only powers (Barricade, ...)
    engine_note: str | None = None   # caveat for statuses the engine only partly implements


def load_table(path: Path, model: type[_Entry], section: str | None = None) -> dict:
    """`{id: model}` for one generated table, validated entry by entry.

    `section` picks a top-level key first, which is how `status_data.json` keeps its
    PLAYER and MONSTER halves in one file.
    """
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if section is not None:
        raw = raw[section]

    table = {}
    for key, entry in raw.items():
        try:
            table[key] = model.model_validate(entry)
        except ValidationError as exc:
            where = f"{path.name}[{section}]" if section else path.name
            raise ValueError(f"{where}: entry {key!r} is malformed\n{exc}") from None
    return table
