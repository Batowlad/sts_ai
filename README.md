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
  produces a `.so`. Linux is the same flow.
- **Docker (Windows/Linux + GPU)** — [Running in Docker](#running-in-docker-windows--gpu);
  needed once training pulls in torch.

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

## Running in Docker (Windows + GPU)

The `Dockerfile` builds a **Linux** image: a CUDA + PyTorch base, the engine
compiled as a Linux `.so`, and `requirements.txt`. Docker Desktop on Windows runs
Linux containers inside a WSL2 VM, so this is the way to get the engine and the
torch/transformers stack into one Python on Windows. The native MSYS2 build can't
do that, because torch ships no mingw wheels. The same image runs unchanged on a
Linux cloud GPU box.

> Not for Apple Silicon: the CUDA base image is x86-only and Macs have no NVIDIA GPU.

### One-time setup
1. Install the latest NVIDIA driver **on Windows itself**. Don't install a
   driver inside WSL; the Windows one is shared into it.
2. Install WSL2 from an **Administrator** PowerShell, then reboot:
   ```powershell
   wsl --install
   ```
3. Install Docker Desktop and tick *Settings → General → Use the WSL 2 based
   engine* (the default on current versions).
4. Check that containers can see the GPU:
   ```powershell
   docker run --rm --gpus all nvidia/cuda:13.2.0-base-ubuntu24.04 nvidia-smi
   ```
   The "CUDA Version" `nvidia-smi` reports must be at least the one in the
   Dockerfile's `FROM` tag (currently 13.2). If it's lower, update the driver or
   pick an older `pytorch/pytorch` tag.

### Build
Clone **with submodules**, or the engine step fails on a missing `pybind11`:
```powershell
git clone --recursive https://github.com/Batowlad/<repo>.git sts_ai
cd sts_ai
docker build -t sts-agent .
```
The first build is slow: it pulls a multi-GB base image and compiles the engine.
The engine and pip layers are cached, so if only Python code changed, just the
final `COPY . .` and the import check rerun. A successful build prints
`engine OK /app/sts_lightspeed/build/slaythespire...so`.

### Run
```powershell
docker run --gpus all -it --rm `
  -v "${PWD}/data:/app/data" `
  -v hf-cache:/root/.cache/huggingface `
  -e ANTHROPIC_API_KEY=$env:ANTHROPIC_API_KEY `
  sts-agent
```
* `--gpus all`: expose the GPU. `-it`: interactive shell (`CMD` is `bash`).
  `--rm`: delete the container on exit; the image stays.
* `-v ...data...`: the host `data\` folder is mounted at `/app/data`, so rollouts
  survive the container. (`data/*` is in `.dockerignore`, so it's never baked in.)
* `-v hf-cache:...`: a Docker named volume for the Hugging Face cache. Without it,
  `--rm` deletes the downloaded base model on exit, and every run downloads it
  again (GBs). The first run fills the volume and later runs load from it. A named
  volume is faster than a Windows folder because it lives inside WSL2. For gated
  models (Llama, Gemma), also pass `-e HF_TOKEN=$env:HF_TOKEN`. To see it or free
  the space: `docker volume ls` / `docker volume rm hf-cache`. For cloud machines,
  the Dockerfile has a commented-out block that builds the weights into the image.
* `-e ANTHROPIC_API_KEY`: pass secrets at run time, never with `ENV` in the Dockerfile.
* The backtick is PowerShell line continuation. In `cmd.exe`, use one line and
  `%cd%` instead of `${PWD}`.

Inside the container (working dir `/app`):
```bash
python -c "import torch; print(torch.cuda.is_available())"   # True
python tests/smoke_test_combat.py
python data/collect_rollouts.py
```

### Iterating without rebuilding
Mount only the Python folders over the image's copy:
```powershell
docker run --gpus all -it --rm -v "${PWD}/env:/app/env" -v "${PWD}/agent:/app/agent" sts-agent
```
Don't mount the whole repo at `/app`. That hides the image's
`sts_lightspeed/build/` (the Linux `.so`) behind your host checkout, and
`import slaythespire` then fails.

### Docker troubleshooting
* **`could not select device driver "" with capabilities: [[gpu]]`**: the
  WSL2 backend is off, or the NVIDIA driver is too old.
* **`torch.cuda.is_available()` is `False`**: the driver's CUDA version is lower
  than the image's. Update the driver or use an older base tag.
* **cmake can't find `pybind11` / `json`**: the repo was cloned without
  `--recursive`. Run `git submodule update --init --recursive`.
* **`manifest unknown` on `FROM`**: that `pytorch/pytorch` tag doesn't exist.
  Pick a real one from Docker Hub.
* **Build is slow or the disk fills up**: give Docker Desktop more disk under
  *Settings → Resources*.
