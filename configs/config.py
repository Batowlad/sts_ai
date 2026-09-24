"""Typed run configuration.

The other trust boundary worth validating: a YAML file a human edits by hand. A typo in
a key or a string where an int belongs should fail at startup with a message naming the
field, not forty minutes into a training run.

    from configs.config import load_config
    cfg = load_config()                      # configs/default.yaml
    cfg = load_config("configs/grpo.yaml")   # anything else
    cfg.env.seed, cfg.rollout.max_steps, ...

`extra="forbid"` means a key this file does not know about is an error rather than a
setting that silently does nothing - the failure mode that makes hand-edited YAML
miserable to debug.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = _REPO_ROOT / "configs" / "default.yaml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EnvConfig(_Section):
    character: str = "IRONCLAD"
    seed: int = 42
    ascension: int = Field(default=0, ge=0, le=20)
    reveal_draw_pile: bool = False      # hidden information; on only for debugging
    # What the prompt describes. Each one costs tokens; eval/metrics.md says how to
    # measure whether it pays for them.
    describe_hand: bool = True          # card text for the hand, in combat
    describe_deck: bool = True          # card text for the deck, out of combat
    route_summary: bool = True          # per-choice room counts on the map screen
    ascii_map: bool = False             # the engine's ASCII map, mostly for debugging


class RolloutConfig(_Section):
    episodes: int = Field(default=1, gt=0)
    max_steps: int = Field(default=2000, gt=0)
    max_battles: int | None = Field(default=None, gt=0)
    out_dir: Path = Path("data/rollouts")
    log_observations: bool = True       # write the full snapshot, not just the action


class PolicyConfig(_Section):
    kind: str = "random"                # 'random' | 'llm' | ...
    model: str = "claude-opus-5"
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0)


class TrainingConfig(_Section):
    algorithm: str = "sft"              # 'sft' | 'grpo' | 'ppo'
    learning_rate: float = Field(default=1e-5, gt=0)
    batch_size: int = Field(default=8, gt=0)
    epochs: int = Field(default=1, gt=0)
    output_dir: Path = Path("training/runs")


class RunConfig(_Section):
    env: EnvConfig = EnvConfig()
    rollout: RolloutConfig = RolloutConfig()
    policy: PolicyConfig = PolicyConfig()
    training: TrainingConfig = TrainingConfig()


def load_config(path: str | Path | None = None) -> RunConfig:
    """Parse and validate a run config. An empty file is valid and means all defaults."""
    path = Path(path) if path is not None else DEFAULT_CONFIG
    if not path.is_absolute():
        path = _REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"no config at {path}")

    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: top level must be a mapping, got {type(raw).__name__}")

    try:
        return RunConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path.name} is invalid\n{exc}") from None


if __name__ == "__main__":
    print(load_config().model_dump_json(indent=2))
