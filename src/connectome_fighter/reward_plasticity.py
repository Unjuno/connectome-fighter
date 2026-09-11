"""Reward-gated plasticity over a fixed set of real MaleCNS KC->MBON edges.

This is a project model extension, not part of MaleCNS and not part of the Shiu
reference LIF model. It never creates/removes edges and never flips transmitter
sign. Positive terminal reward depresses recently co-active KC->MBON synapses;
negative terminal reward strengthens them. This anti-Hebbian direction is
inspired by dopamine-gated KC->MBON plasticity, but using a single game reward
as the modulatory signal is an engineering abstraction and must be logged as
such.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

PLASTICITY_SCHEMA = 1


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class RewardPlasticityConfig:
    learning_rate: float = 0.02
    eligibility_decay_per_decision: float = 0.9
    pair_count_cap: float = 25.0
    multiplier_min: float = 0.5
    multiplier_max: float = 1.5
    normalization_percentile: float = 95.0

    def validate(self) -> None:
        if not (0 < self.learning_rate <= 1):
            raise ValueError("learning_rate must be in (0,1]")
        if not (0 < self.eligibility_decay_per_decision <= 1):
            raise ValueError("eligibility decay must be in (0,1]")
        if self.pair_count_cap <= 0:
            raise ValueError("pair count cap must be positive")
        if not (0 < self.multiplier_min <= 1 <= self.multiplier_max):
            raise ValueError("multiplier bounds must contain 1")
        if not (0 < self.normalization_percentile <= 100):
            raise ValueError("normalization percentile must be in (0,100]")

    def fingerprint(self) -> str:
        self.validate()
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


@dataclass
class PlasticityState:
    character: str
    multipliers: np.ndarray
    generation: int
    matches: int
    updates: int
    candidate_sha256: str
    config_sha256: str

    def validate(self, n_candidates: int) -> None:
        if self.multipliers.shape != (n_candidates,):
            raise ValueError("plasticity multiplier shape mismatch")
        if not np.isfinite(self.multipliers).all() or np.any(self.multipliers <= 0):
            raise ValueError("plasticity multipliers must be finite and positive")
        if min(self.generation, self.matches, self.updates) < 0:
            raise ValueError("plasticity counters must be non-negative")
        if not self.character or not self.candidate_sha256 or not self.config_sha256:
            raise ValueError("plasticity state identity is incomplete")


def initialize_state(
    *, character: str, n_candidates: int, candidate_sha256: str,
    config: RewardPlasticityConfig,
) -> PlasticityState:
    config.validate()
    state = PlasticityState(
        character=str(character),
        multipliers=np.ones(n_candidates, dtype=np.float32),
        generation=0,
        matches=0,
        updates=0,
        candidate_sha256=str(candidate_sha256),
        config_sha256=config.fingerprint(),
    )
    state.validate(n_candidates)
    return state


def save_state(path: str | Path, state: PlasticityState) -> dict[str, Any]:
    path = Path(path)
    state.validate(len(state.multipliers))
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "schema_version": PLASTICITY_SCHEMA,
        "character": state.character,
        "generation": int(state.generation),
        "matches": int(state.matches),
        "updates": int(state.updates),
        "candidate_sha256": state.candidate_sha256,
        "config_sha256": state.config_sha256,
        "n_candidates": int(len(state.multipliers)),
        "multiplier_min": float(state.multipliers.min()),
        "multiplier_max": float(state.multipliers.max()),
        "multiplier_mean": float(state.multipliers.mean()),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        np.savez_compressed(f, multipliers=state.multipliers.astype(np.float32))
    tmp.replace(path)
    meta["state_sha256"] = sha256_file(path)
    path.with_suffix(path.suffix + ".json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return meta


def load_state(
    path: str | Path,
    *, expected_character: str,
    n_candidates: int,
    expected_candidate_sha256: str,
    expected_config_sha256: str,
) -> PlasticityState:
    path = Path(path)
    meta_path = path.with_suffix(path.suffix + ".json")
    if not path.is_file() or not meta_path.is_file():
        raise FileNotFoundError(path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("schema_version") != PLASTICITY_SCHEMA:
        raise ValueError("unsupported plasticity state schema")
    if meta.get("character") != expected_character:
        raise ValueError("plasticity state belongs to another character")
    if meta.get("candidate_sha256") != expected_candidate_sha256:
        raise ValueError("plasticity candidate hash mismatch")
    if meta.get("config_sha256") != expected_config_sha256:
        raise ValueError("plasticity config hash mismatch")
    if meta.get("state_sha256") != sha256_file(path):
        raise ValueError("plasticity state checksum mismatch")
    with np.load(path, allow_pickle=False) as z:
        multipliers = z["multipliers"].astype(np.float32, copy=True)
    state = PlasticityState(
        character=expected_character,
        multipliers=multipliers,
        generation=int(meta["generation"]),
        matches=int(meta["matches"]),
        updates=int(meta["updates"]),
        candidate_sha256=expected_candidate_sha256,
        config_sha256=expected_config_sha256,
    )
    state.validate(n_candidates)
    return state


def apply_terminal_reward(
    state: PlasticityState,
    eligibility: np.ndarray,
    reward: float,
    config: RewardPlasticityConfig,
) -> dict[str, Any]:
    config.validate()
    if reward not in (-1.0, 0.0, 1.0):
        raise ValueError("terminal reward must be -1, 0, or +1")
    eligibility = np.asarray(eligibility, dtype=np.float64)
    if eligibility.shape != state.multipliers.shape or not np.isfinite(eligibility).all():
        raise ValueError("invalid eligibility vector")
    if np.any(eligibility < 0):
        raise ValueError("eligibility must be non-negative")

    before = state.multipliers.astype(np.float64, copy=True)
    positive = eligibility[eligibility > 0]
    scale = float(np.percentile(positive, config.normalization_percentile)) if len(positive) else 0.0
    if scale > 0 and reward != 0:
        normalized = np.clip(eligibility / scale, 0.0, 1.0)
        # Project extension: game reward modulates anti-Hebbian KC->MBON
        # plasticity. +1 depresses eligible edges; -1 strengthens them.
        log_change = -config.learning_rate * reward * normalized
        after = before * np.exp(log_change)
        after = np.clip(after, config.multiplier_min, config.multiplier_max)
        state.multipliers = after.astype(np.float32)
        changed = int(np.count_nonzero(np.abs(after - before) > 1e-12))
        state.updates += 1
    else:
        changed = 0
    state.matches += 1
    state.generation += 1
    return {
        "reward": float(reward),
        "eligibility_nonzero": int(np.count_nonzero(eligibility)),
        "eligibility_scale": scale,
        "changed_edges": changed,
        "multiplier_min_before": float(before.min()),
        "multiplier_max_before": float(before.max()),
        "multiplier_min_after": float(state.multipliers.min()),
        "multiplier_max_after": float(state.multipliers.max()),
        "multiplier_mean_after": float(state.multipliers.mean()),
    }
