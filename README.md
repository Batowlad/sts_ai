# sts-llm-agent

LLM agent for Slay the Spire, on top of the vendored `sts_lightspeed` C++ engine.

## Layout
```
env/        # game_interface (wraps sts_lightspeed), state_encoder, action_parser
agent/      # policy (LLM-as-policy), prompts
data/       # collect_rollouts.py + generated datasets
training/   # sft, rl (GRPO/PPO), reward
eval/       # evaluate, metrics
configs/    # yaml/json configs
notebooks/  # exploration, plotting
sts_lightspeed/  # vendored C++ engine + pybind11 module (build separately)
```

## Building the engine

The `slaythespire` Python module is a pybind11 wrapper around the C++17
`sts_lightspeed` engine. On Windows it is built with the **MSYS2 + mingw64**
toolchain. The resulting `.pyd` is ABI-locked to MSYS2's MINGW64 Python and will
**not** import from a python.org / MSVC Python.

### Prerequisites
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

### Configure & build
From the **MSYS2 MINGW64** shell, in `sts_lightspeed/`:
```bash
cd /d/Dev/sts_ai/sts_lightspeed

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

### Running
The module only imports from MSYS2's MINGW64 Python 3.14 with `/mingw64/bin` on
`PATH`. From the MSYS2 MINGW64 shell:
```bash
cd /d/Dev/sts_ai/sts_lightspeed/cmake-build-mingw && python yourscript.py
```
Or from PowerShell:
```powershell
$env:MSYSTEM = "MINGW64"
& C:\msys64\usr\bin\bash.exe -lc "cd /d/Dev/sts_ai/sts_lightspeed/cmake-build-mingw && python yourscript.py"
```

Once built, from MSYS2 MINGW64 Python:
```python
from env.game_interface import sts, new_game
gc = new_game(seed=42)
print(gc.cur_hp, gc.deck)
```
Set `STS_BUILD_DIR` / `STS_MINGW_BIN` if your paths differ from the defaults.

### Troubleshooting
* **`ImportError` / DLL load failed** — you're using the wrong Python. Only the
  MSYS2 MINGW64 Python 3.14 can import the mingw-compiled `.pyd`; an MSVC Python
  (python.org / Microsoft Store) fails with an ABI mismatch.
* **CMake grabs the wrong Python** — pass the `-DPython_EXECUTABLE` /
  `-DPython_ROOT_DIR` flags above explicitly.
* **`constexpr` / C++17 errors** — make sure you're compiling with the mingw64
  gcc, not an older system compiler.
