# Eval metrics

What to measure when comparing policies or prompt formats, and the factors that move
the numbers. `eval/metrics.py` will compute these once `eval/evaluate.py` can run games.

## Outcome metrics

- **Win rate**: runs that beat the act 3 boss (act 4 later).
- **Floor reached**: mean and median; more informative than win rate while the policy is weak.
- **HP lost per fight**, split by normal, elite and boss.
- **Invalid-output rate**: replies that don't parse, or name a key that isn't legal.

## Cost metrics

- **Prompt tokens per step**, split by screen (BATTLE, MAP_SCREEN, REWARDS, ...).
- **Prompt tokens per run**: per-step tokens times the number of steps. This drives
  training and inference cost.

## Factor: what the prompt describes

Token count depends partly on the game state (hand size, deck size, number of enemies,
how many statuses are on). It also depends on how much of that state the prompt
describes. Those descriptions can be switched on and off, so they are an experiment
variable. Each switch is a keyword argument of `render()` (`env/render.py`) and a
field under `env:` in `configs/default.yaml`:

| Switch          | Default | What it adds                                            |
|-----------------|---------|---------------------------------------------------------|
| `describe_hand` | on      | Card text for every distinct card in hand (combat)      |
| `describe_deck` | on      | Card text for every distinct card in the deck (out of combat) |
| `route_summary` | on      | Map: per choice, fewest-most fights/elites/events/rests/shops to the boss |
| `ascii_map`     | off     | Map: the engine's ASCII drawing with your position as `X` |

`reveal_draw_pile` also changes token count, but it leaks hidden information. It is a
debugging switch, not an experiment variable.

### Measured cost

Mean Qwen2.5 chat-template tokens per state, for 226 states from 3 random-policy runs
(seeds 0-2). Every run died in act 1, so the decks are small; later acts will cost more.

| Config             | BATTLE | MAP_SCREEN | REWARDS | EVENT_SCREEN |
|--------------------|-------:|-----------:|--------:|-------------:|
| all defaults       | 299    | 290        | 261     | 196          |
| `describe_hand` off | 254 (−45) | –      | –       | –            |
| `describe_deck` off | –      | 218 (−72)  | 193 (−68) | 129 (−67)  |
| `route_summary` off | –      | 215 (−75)  | –       | –            |
| `ascii_map` on     | –      | 553 (+263) | –       | –            |

("–" = unchanged.) The deck glossary grows with every distinct card added, so a
late-game deck costs more than these numbers. The hand glossary stays capped at the
hand size.

### Evaluating the difference later

Token cost is only half of it. A description is worth keeping when the policy plays
measurably better with it. The plan, once an LLM policy exists:

1. **One switch at a time.** Start from the defaults, flip one switch, and hold
   everything else fixed: model, checkpoint, sampling temperature, seed list.
2. **Same seeds for every arm.** Run each config on the same list of game seeds, so
   differences come from the prompt and not the map or card draws. Compare paired per
   seed.
3. **Match train and eval.** A model fine-tuned with descriptions will read a prompt
   without them as out of distribution. For a fair comparison, fine-tune one model per
   config, or at least train on a mix of configs.
4. **Look at the screen the switch affects.** `route_summary` should show up in map
   choices (elites fought, rests reached, HP entering the boss), not in win rate first.
   `describe_deck` should show up in card picks, removals and upgrades.
5. **Report both columns.** For each switch: change in tokens per run, and change in
   floor reached / win rate / invalid-output rate, with a confidence interval over seeds.
   Drop a description if it costs tokens without a measurable gain.

Questions this should answer:

- Does a small model (Qwen2.5-1.5B) need card text at all after fine-tuning, or does it
  learn cards by name? If so, the descriptions may only matter early in training.
- Does the route summary beat the ASCII map, as expected, and does anything beat
  having no map information?
- Does a long deck glossary crowd out the rest of the prompt late in the game?

To reproduce the token table, render the same saved `Observation`s under each config and
count with `env.state_encoder.tokenize_state`.
