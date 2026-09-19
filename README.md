# sts-ai-agent

LLM agent for Slay the Spire, on top of the vendored `sts_lightspeed` C++ engine.

## Layout
```
env/        # game_interface (wraps sts_lightspeed), game_types, observe, render,
            #   state_encoder, action_parser
agent/      # policy (LLM-as-policy), prompts
data/       # collect_rollouts.py + generated datasets
training/   # sft, rl (GRPO/PPO), reward
eval/       # evaluate, metrics
configs/    # config.py (typed RunConfig) + default.yaml
game_data/  # schemas.py + the generated card/relic/potion/status tables
notebooks/  # exploration, plotting
sts_lightspeed/  # vendored C++ engine + pybind11 module (build separately)
```

## Typed state and actions

The engine is read into frozen dataclasses before anything renders text, so the
structure survives for reward shaping, rollout logging and eval:

```
pybind objects --observe.py--> Observation / ActionOption --render.py--> str
```

```python
from dataclasses import asdict
from env.game_interface import GameInterface

gi = GameInterface()
obs = gi.observe()                    # Observation - detached snapshot
opts = gi.legal_action_options()      # tuple[ActionOption, ...] - typed legal moves
row = asdict(obs)                     # plain dict, straight into json.dumps
gi.step(opts[0])                      # step by option, index, or engine Action
```

* `env/game_types.py` — the dataclasses. No engine import, so it stays cycle-free.
* `env/observe.py` — builders. The only module that imports both sides.
* `env/render.py` — `render(obs) -> str`. Pure, so it is testable without the engine.
* `env/state_encoder.py` — `encode_state(gi)` is now `render(build_observation(gi))`.
* `env/action_parser.py` — `parse_structured_action(text, gi)` reads the policy's JSON
  commitment; `parse_action(text, gi, encode_state)` is the natural-language path, kept
  for the describe/view queries and the REPL.

`step()` takes an `ActionOption.key` (`'play_card:BASH->0'`), an `ActionOption`, an
index, or an engine action. Keys are what the prompt lists and what the policy answers
with: an index is only valid for the step that produced it, while a key names the
decision itself, so the prompt, the rollout log and the reward all refer to one string.
`bits` + `screen` let `step()` replay an option exactly.

Snapshots capture everything the engine exposes, including the draw pile's order;
`render` hides it unless you pass `reveal_draw_pile=True`, so the policy is not
trained on information it will not have at inference.

Pydantic sits only at the trust boundaries — `game_data/schemas.py` validates the
generated JSON tables once at import, and `configs/config.py` validates the YAML.
The per-step types stay plain dataclasses: they are built thousands of times per
rollout from data the C++ engine already validated.

Tests: `python tests/test_typed_layer.py`.

## Building the engine

The `slaythespire` Python module is a pybind11 wrapper around the C++17
`sts_lightspeed` engine. The compiled artifact is ABI-locked to the exact Python
it was built against, so always build it with the interpreter you intend to run.

- **Windows** — [MSYS2 + mingw64](#windows-msys2--mingw64); produces a `.pyd`.
- **macOS** — [Apple `clang` + `cmake`/`ninja`](#macos-apple-silicon--intel);
  produces a `.so`. Linux is the same flow (see also the `Dockerfile`).

### Windows (MSYS2 + mingw64)

The resulting `.pyd` is ABI-locked to MSYS2's MINGW64 Python and will **not**
import from a python.org / MSVC Python.

#### Prerequisites
1. Install [MSYS2](https://www.msys2.org/) (default location `C:\msys64`).
2. From the **MSYS2 MINGW64** shell, install the toolchain:
   ```bash
   pacman -S --needed \
     mingw-w64-x86_64-gcc \
     mingw-w64-x86_64-cmake \
     mingw-w64-x86_64-ninja \
     mingw-w64-x86_64-python \
     mingw-w64-x86_64-python-pip
   ```
3. Initialize submodules (engine + pybind11 + json) if you haven't already:
   ```bash
   git submodule update --init --recursive
   ```

#### Configure & build
From the **MSYS2 MINGW64** shell, in `sts_lightspeed/`:
```bash
# MSYS2 maps Windows drives to /<drive-letter>/, e.g. D:\dev\sts_ai -> /d/dev/sts_ai
cd /path/to/sts_ai/sts_lightspeed

# Force the mingw Python (otherwise CMake may pick up a registry MSVC Python)
cmake -G Ninja -S . -B cmake-build-mingw -DCMAKE_BUILD_TYPE=Release \
  -DPYBIND11_FINDPYTHON=NEW \
  -DPython_EXECUTABLE=/mingw64/bin/python.exe \
  -DPython_ROOT_DIR=/mingw64

# Build the Python module
cmake --build cmake-build-mingw --target slaythespire -j
```
This produces `cmake-build-mingw/slaythespire.cp314-mingw_x86_64_msvcrt_gnu.pyd`.

The console simulator and benchmark/agent targets build the same way:
```bash
cmake --build cmake-build-mingw --target main -j   # console sim
cmake --build cmake-build-mingw --target test -j   # benchmarks / agents
```

#### Running
The module only imports from MSYS2's MINGW64 Python 3.14 with `/mingw64/bin` on
`PATH`. From the MSYS2 MINGW64 shell:
```bash
cd /path/to/sts_ai/sts_lightspeed/cmake-build-mingw && python yourscript.py
```
Or from PowerShell:
```powershell
$env:MSYSTEM = "MINGW64"
& C:\msys64\usr\bin\bash.exe -lc "cd /path/to/sts_ai/sts_lightspeed/cmake-build-mingw && python yourscript.py"
```

Once built, from MSYS2 MINGW64 Python:
```python
from env.game_interface import sts, new_game
gc = new_game(seed=42)
print(gc.cur_hp, gc.deck)
```
Set `STS_BUILD_DIR` / `STS_MINGW_BIN` if your paths differ from the defaults.

> **Note:** `.vscode/launch.json` hardcodes the MSYS2 default Python at
> `C:\msys64\mingw64\bin\python.exe` — VS Code launch configs can't fall back to
> an environment variable, so if MSYS2 is installed elsewhere you must edit the
> `python` and `PATH` entries there by hand.

### macOS (Apple Silicon / Intel)

On macOS the engine builds as a native `.so` with Apple `clang` + `cmake`/`ninja`
— no MSYS2. Build against the same interpreter (ideally a venv) you'll run.

#### Prerequisites
1. Xcode Command Line Tools (provides `clang`):
   ```bash
   xcode-select --install
   ```
2. [Homebrew](https://brew.sh/), then the build tools:
   ```bash
   brew install cmake ninja
   ```
3. Initialize submodules (engine + pybind11 + json) if you haven't already:
   ```bash
   git submodule update --init --recursive
   ```

#### Configure & build
Build against a venv so the module matches the Python you run:
```bash
cd /path/to/sts_ai
python3 -m venv .venv
source .venv/bin/activate

cd sts_lightspeed
cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DPYBIND11_FINDPYTHON=ON \
  -DPython_EXECUTABLE="$(which python)"
cmake --build build --target slaythespire -j
```
This produces `sts_lightspeed/build/slaythespire.*.so`. The `main` (console sim),
`test` (benchmarks/agents) and `small-test` targets build the same way; a bare
`cmake --build build -j` builds all four.

> **CMake 4.x note:** Homebrew ships CMake 4.x, which rejects the pre-3.5
> `cmake_minimum_required` in the vendored `json` submodule. The top-level
> `CMakeLists.txt` now defaults `CMAKE_POLICY_VERSION_MINIMUM` to `3.5` for the
> subprojects, so no extra flag is needed. Pass `-DCMAKE_POLICY_VERSION_MINIMUM=...`
> yourself to override that.

#### Running
`game_interface.py` probes `sts_lightspeed/{build,cmake-build-mingw,cmake-build-release,cmake-build-debug}`
for a compiled `slaythespire` module, so the macOS build is picked up with no
configuration:
```bash
cd /path/to/sts_ai
python -c "from env.game_interface import sts, new_game; \
gc = new_game(seed=42); print(gc.cur_hp, gc.deck)"
```
Set `STS_BUILD_DIR` only if your build lives somewhere else — it short-circuits the
probe. `STS_MINGW_BIN` is Windows-only and is ignored on macOS/Linux.

Then run the tests: `python tests/test_typed_layer.py` and
`python tests/smoke_test_combat.py`.

### Troubleshooting
* **`ImportError` / DLL load failed** — you're using the wrong Python. Only the
  MSYS2 MINGW64 Python 3.14 can import the mingw-compiled `.pyd`; an MSVC Python
  (python.org / Microsoft Store) fails with an ABI mismatch.
* **CMake grabs the wrong Python** — pass the `-DPython_EXECUTABLE` /
  `-DPython_ROOT_DIR` flags above explicitly.
* **`constexpr` / C++17 errors** — make sure you're compiling with the mingw64
  gcc, not an older system compiler.
* **(macOS) `Compatibility with CMake < 3.5 has been removed`** — CMake 4.x vs.
  the old `json` submodule. The top-level `CMakeLists.txt` handles this; if you
  see it, your `sts_lightspeed` submodule predates that fix — update it, or add
  `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` to the `cmake` configure command.
* **(macOS) `ImportError` on `import slaythespire`** — the `.so` was built against
  a different Python than the one importing it. Rebuild inside the venv you run
  from (so `-DPython_EXECUTABLE="$(which python)"` picks it up). The raised error
  lists the directories that were probed and the interpreter in use.
* **`AttributeError: 'slaythespire.GameContext' object has no attribute ...`** —
  the compiled module is older than the Python layer that calls it. Pull the
  submodule (`git submodule update --remote sts_lightspeed`, or `git pull` inside
  it) and rebuild; the bindings and `env/observe.py` move together.
