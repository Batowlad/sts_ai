# Recommendations

A running log of design decisions and things worth doing later, so the reasoning
survives longer than the conversation it came out of.

One `##` section per topic, newest at the bottom. Each entry gets a date, a verdict
in one line, and the reasoning under it. When something here gets done or overturned,
mark the verdict `Done` / `Superseded` rather than deleting the entry — the rejected
options are the useful part.

## Pydantic: where it belongs

*2026-09-19 — Verdict: keep the current boundary rule. No new pydantic in `env/`.*

The rule already in the code: pydantic at trust boundaries, frozen dataclasses
everywhere else. Stated at `game_data/schemas.py:8-11` and `configs/config.py:1-14`.

The two boundaries that are validated today are the right ones:

* `game_data/schemas.py` — the generated `*_data.json` tables. The builder and the
  reader can drift apart, and `extra="forbid"` turns that into one clear message
  instead of a `KeyError` deep in a prompt render.
* `configs/config.py` — `default.yaml`, edited by hand. A typo in a key should fail
  at startup, not forty minutes into a training run.

Where it does **not** belong:

* `env/action_parser.py` — maps free text to a method call. There is no schema to
  validate, the input is already normalized to a word list, and the failure mode is
  a clear `ValueError` at `env/action_parser.py:223`.
* `env/game_types.py` — `Observation` / `ActionOption` are built thousands of times
  per rollout from data the C++ engine has already validated, and
  `dataclasses.asdict` already yields JSON-ready dicts. Re-validating each field is
  pure overhead on the hottest path.

### Next place it earns its keep: the rollout log

`dump_state` (`env/state_encoder.py:41`) writes `data/state_dump.jsonl`;
`data/collect_rollouts.py` and `training/sft.py` are still stubs. The moment `sft.py`
reads those records back, that file becomes a real boundary — jsonl written by an
older revision of the encoder, possibly on another machine, with fields that came and
went.

* Validate on **read**, in the training loader. Not on write in `dump_state`, which
  is on the hot path.
* Add a `schema_version` int to the record now, while the format still has exactly
  one writer.

The other future spot is `agent/policy.py`: if the policy ever moves from free text
to structured output instead of going through `parse_action`, validating what the
model emits is a boundary by definition.

## Policy output: JSON commitment instead of parsed prose

*2026-09-19 — Verdict: Done. Reasoning stays free text; the action is a JSON object
naming one `ActionOption.key`.*

The free-text path could not express the action space and silently misread it. Probed
with plausible model sentences, the old `parse_action` fallback — any digit anywhere in
the text is an index into `legal_actions()` — gave:

| model says | old parser did |
| --- | --- |
| "play Bash on monster 0 to set up the Vulnerable" | `step(0)` — the *target* became the action |
| "Strike the front enemy, it only has 2 hp left" | `step(2)` — an *HP number* became the action |
| "Defend. I have 3 block already" | `step(3)` — a *block count* became the action |
| "I'll end the turn" | `ValueError` — unreachable |

Under GRPO that is parser noise in the gradient: the model is rewarded for actions it
never chose, and the log and the engine disagree about what happened.

JSON rather than a terse DSL, on long-term grounds rather than token count (the
commitment is a few percent of a step's generation either way):

* One pydantic model gives validation on read, a JSON Schema for constrained decoding,
  and a tool definition for a teacher model. A hand-rolled grammar gives none of those,
  and you keep a parser, a grammar and a prompt in sync by hand forever.
* Versioned records migrate. An ad-hoc string grammar rots silently — an old record
  parsed under new rules yields a plausible-but-wrong action, the same failure class,
  moved to dataset time where it is harder to notice.
* JSON Schema is what serving stacks' constrained decoding and teachers' structured
  output modes already consume, so swapping model or stack costs nothing.
* Instruct models have seen enormous amounts of JSON; a bespoke DSL exists only in our
  SFT data, which bites hardest at the cold start, before that data exists.

Two decisions that matter more than the format:

* **The value is a closed enum of the current legal keys**, not a field per argument.
  `{"action": "play_card:BASH->0"}` is either in the legal set or is not; separate
  `card`/`target` fields can spell a well-formed illegal action (a card not in hand, a
  dead target) and hand us a validation and reward-shaping problem the engine already
  solved.
* **Reasoning stays outside the JSON.** Long CoT inside a JSON string means escaping
  newlines and quotes, and the object cannot be parsed until the string closes.

### Still open

* Rollout records need a `schema_version` int as soon as `data/collect_rollouts.py`
  writes them, while the format has exactly one writer. Validate on read in the training
  loader, never on write in `dump_state` — that is the hot path.
* Grammar-constrained decoding belongs at the serving layer, later. With a single enum
  field the grammar is a choice over N literal strings, so illegal actions become
  impossible rather than penalized.
* Queries (`describe`, `view_*`) are still natural language. If the policy should ask
  questions mid-episode, they become a second JSON verb rather than a keyword match.
