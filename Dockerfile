# =============================================================================
# Starter Dockerfile for sts-llm-agent (GPU training / eval in the cloud)
#
# This builds the sts_lightspeed engine as a LINUX .so (NOT the Windows .pyd you
# build locally) from the committed C++ source, then installs the Python deps.
# Same git source, different compiled artifact -- that's expected.
#
# Build:  docker build -t sts-agent .
# Run (GPU): docker run --gpus all -it --rm -v "$PWD/data:/app/data" sts-agent
# Run (CPU): docker run -it --rm sts-agent
# =============================================================================

# --- Base image -------------------------------------------------------------
# Default is a CUDA + PyTorch runtime so the GPU is ready for training/RL.
# LATER: pin the CUDA version to match your cloud GPU's driver (run `nvidia-smi`
#        on the instance to see the max CUDA it supports), and bump the torch tag.
#        For CPU-only work (Claude-API policy, rollout collection, eval) you can
#        swap this for a much smaller base:  FROM python:3.12-slim
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

# Non-interactive apt + no .pyc clutter + unbuffered logs for live training output
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- Build toolchain for the C++ engine -------------------------------------
# The pytorch *runtime* base has no compilers, so install them. No MSYS2/mingw
# here -- on Linux the engine builds with plain gcc/cmake/ninja.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        ninja-build \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Build the slaythespire module ------------------------------------------
# Copy only the engine first so this layer is cached and doesn't rebuild every
# time you touch Python code.
COPY sts_lightspeed/ ./sts_lightspeed/

# Build against THIS image's python (likely 3.11/3.12 -- different from your
# local MSYS2 3.14, which is fine; it's an independent build). pybind11 finds it.
RUN cmake -G Ninja -S sts_lightspeed -B sts_lightspeed/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DPYBIND11_FINDPYTHON=ON \
        -DPython_EXECUTABLE="$(which python)" \
    && cmake --build sts_lightspeed/build --target slaythespire -j

# Point game_interface.py at the Linux build dir via the env override it supports
# (its default is the Windows cmake-build-mingw dir).
ENV STS_BUILD_DIR=/app/sts_lightspeed/build

# --- Python dependencies ----------------------------------------------------
# LATER: fill in requirements.txt (torch is already in the base image, so you
#        usually do NOT re-pin it here -- list transformers, trl, datasets,
#        accelerate, peft, anthropic, pyyaml, etc.). Keep this above the source
#        COPY so dep installs stay cached across code edits.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Project code -----------------------------------------------------------
COPY . .

# Sanity check that the engine imports inside the image (remove if it slows builds)
RUN python -c "import slaythespire as s; print('engine OK', s.__file__)"

# --- Default command --------------------------------------------------------
# LATER: replace with your real entrypoint, e.g.
#        CMD ["python", "-m", "training.rl", "--config", "configs/default.yaml"]
CMD ["bash"]

# =============================================================================
# TODO checklist when you actually need this:
#   [ ] Match CUDA tag to the cloud GPU driver (nvidia-smi).
#   [ ] Populate requirements.txt (don't double-install torch from the base).
#   [ ] Mount data/ and checkpoints as volumes so results survive the container:
#         -v "$PWD/data:/app/data" -v "$PWD/checkpoints:/app/checkpoints"
#   [ ] Pass secrets at runtime, never bake them in:  -e ANTHROPIC_API_KEY=...
#   [ ] Set a real CMD (training/eval entrypoint).
#   [ ] (Optional) Multi-stage build: compile the .so in a builder stage, copy
#       just the .so into a slim runtime image to shrink the final image.
#   [ ] (Optional) Pre-download / cache the HF base model to avoid re-pulling it.
# =============================================================================
