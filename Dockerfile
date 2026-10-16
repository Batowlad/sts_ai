# =============================================================================
# Starter Dockerfile for sts-llm-agent (GPU training / eval in the cloud)
#
# This builds the sts_lightspeed engine as a LINUX .so (NOT the Windows .pyd you
# build locally) from the committed C++ source, then installs the Python deps.
# Same git source, different compiled artifact -- that's expected.
#
# Build:  docker build -t sts-agent .
# Run (GPU): docker run --gpus all --ipc=host -it --rm -v "$PWD/data:/app/data" \
#                -v hf-cache:/root/.cache/huggingface sts-agent
#   --ipc=host: vLLM passes data between its processes through shared memory,
#   and Docker's default 64 MB /dev/shm is too small (or use --shm-size=8g).
# Run (CPU): docker run -it --rm sts-agent
# =============================================================================

# --- Base image -------------------------------------------------------------
# Default is a CUDA + PyTorch runtime so the GPU is ready for training/RL.
# LATER: pin the CUDA version to match your cloud GPU's driver (run `nvidia-smi`
#        on the instance to see the max CUDA it supports), and bump the torch tag.
#        For CPU-only work (random-policy rollout collection, eval) you can
#        swap this for a much smaller base:  FROM python:3.12-slim
# The -runtime tag has no nvcc. If vLLM/FlashInfer fails at runtime with a JIT
# compile error or "nvcc not found", switch to the matching -devel tag.
FROM pytorch/pytorch:2.13.0-cuda13.2-cudnn9-runtime

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

# --- Python dependencies ----------------------------------------------------
# torch is already in the base image; vllm pins the exact torch it needs, which
# matches the base, so pip leaves it alone. This is the slowest layer (vllm,
# flashinfer, transformers = several GB), so it goes first: engine or code edits
# then reuse the cached install instead of redoing it.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt ./
RUN uv pip install --no-cache -r requirements.txt

# --- Build the slaythespire module ------------------------------------------
# Copy only the engine (not the whole repo) so this layer is cached and doesn't
# rebuild every time you touch Python code.
COPY sts_lightspeed/ ./sts_lightspeed/

# Build against THIS image's python (likely 3.11/3.12 -- different from your
# local MSYS2 3.14, which is fine; it's an independent build). pybind11 finds it.
RUN cmake -G Ninja -S sts_lightspeed -B sts_lightspeed/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DPYBIND11_FINDPYTHON=ON \
        -DPython_EXECUTABLE="$(which python)" \
    && cmake --build sts_lightspeed/build --target slaythespire -j

# game_interface.py would find /app/sts_lightspeed/build on its own, but pin it
# explicitly so the image never depends on that probe order.
# STS_BUILD_DIR is only read by game_interface.py; Python itself ignores it. Also
# put the dir on PYTHONPATH so a bare `import slaythespire` works anywhere in the
# container (the sanity check below, notebooks, one-off scripts).
ENV STS_BUILD_DIR=/app/sts_lightspeed/build \
    PYTHONPATH=/app/sts_lightspeed/build

# --- (Optional) Base model weights baked into the image ---------------------
# By default from_pretrained() downloads to ~/.cache/huggingface at run time, and
# --rm throws that away on exit. Locally, mount a volume instead (see README:
# -v hf-cache:/root/.cache/huggingface). Uncomment this for cloud boxes that start
# fresh each time: +model size on the image, but no download per run.
# Stays above COPY . . so code edits don't trigger a re-download; changing
# BASE_MODEL (or --build-arg BASE_MODEL=...) does.
# Gated models (Llama, Gemma) need a token. Use a build secret, never ENV HF_TOKEN:
#   RUN --mount=type=secret,id=hf_token HF_TOKEN=$(cat /run/secrets/hf_token) python -c ...
#   docker build --secret id=hf_token,env=HF_TOKEN -t sts-agent .
# ENV HF_HOME=/opt/hf
# ARG BASE_MODEL=Qwen/Qwen3-8B
# RUN python -c "from huggingface_hub import snapshot_download; \
# snapshot_download('${BASE_MODEL}', allow_patterns=['*.json', '*.safetensors', 'tokenizer*'])"

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
#   [X] Match CUDA tag to the cloud GPU driver (nvidia-smi).
#   [X] Populate requirements.txt (don't double-install torch from the base).
#   [ ] Mount data/ and checkpoints as volumes so results survive the container:
#         -v "$PWD/data:/app/data" -v "$PWD/checkpoints:/app/checkpoints"
#   [ ] Set a real CMD (training/eval entrypoint).
#   [ ] (Optional) Multi-stage build: compile the .so in a builder stage, copy
#       just the .so into a slim runtime image to shrink the final image.
#   [ ] (Optional) Pre-download / cache the HF base model to avoid re-pulling it
#       (hf-cache volume locally; uncomment the "Base model weights" block for cloud).
# =============================================================================
