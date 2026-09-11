"""Apply a character-specific KC->MBON magnitude state to a Shiu Synapses object."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib

import numpy as np
import pandas as pd
from brian2 import mV

from .reward_plasticity import (
    RewardPlasticityConfig,
    initialize_state,
    load_state,
    sha256_file,
)


def apply_character_plasticity(
    recurrent_syn: Any,
    *,
    character: str,
    candidates_path: str | Path,
    state_path: str | Path | None,
    config: RewardPlasticityConfig = RewardPlasticityConfig(),
) -> dict:
    """Apply multipliers after upstream Shiu create_model(), before baseline store.

    Exact pre/post indices are checked against the candidate artifact before any
    weight is changed. This guards against silently applying a checkpoint to a
    differently ordered connectivity table.
    """
    candidates_path = Path(candidates_path)
    candidates = pd.read_parquet(candidates_path)
    required = {"synapse_index", "pre_index", "post_index", "sign"}
    if not required.issubset(candidates.columns) or candidates.empty:
        raise ValueError("Invalid KC->MBON candidate file")
    if not (candidates["sign"] == 1).all():
        raise ValueError("Candidate sign invariant violated")
    synapse_idx = candidates["synapse_index"].to_numpy(dtype=np.int64)
    expected_pre = candidates["pre_index"].to_numpy(dtype=np.int64)
    expected_post = candidates["post_index"].to_numpy(dtype=np.int64)
    actual_pre = np.asarray(recurrent_syn.i[synapse_idx], dtype=np.int64)
    actual_post = np.asarray(recurrent_syn.j[synapse_idx], dtype=np.int64)
    if not np.array_equal(actual_pre, expected_pre) or not np.array_equal(actual_post, expected_post):
        raise ValueError("Candidate synapse indices do not match current Shiu connectivity ordering")

    candidate_sha = sha256_file(candidates_path)
    config_sha = config.fingerprint()
    state_path = Path(state_path) if state_path else None
    if state_path is not None and state_path.is_file():
        state = load_state(
            state_path,
            expected_character=character,
            n_candidates=len(candidates),
            expected_candidate_sha256=candidate_sha,
            expected_config_sha256=config_sha,
        )
        source = "checkpoint"
        state_sha = sha256_file(state_path)
    else:
        state = initialize_state(
            character=character,
            n_candidates=len(candidates),
            candidate_sha256=candidate_sha,
            config=config,
        )
        source = "unity-initial-state"
        state_sha = hashlib.sha256(state.multipliers.tobytes()).hexdigest()

    base_mV = np.asarray(recurrent_syn.w[synapse_idx] / mV, dtype=np.float64)
    if np.any(base_mV <= 0):
        raise ValueError("KC->MBON candidate base weights must remain excitatory/positive")
    applied_mV = base_mV * state.multipliers.astype(np.float64)
    recurrent_syn.w[synapse_idx] = applied_mV * mV
    # Re-read the assigned values; fail if Brian2 indexing semantics changed.
    observed_mV = np.asarray(recurrent_syn.w[synapse_idx] / mV, dtype=np.float64)
    if not np.allclose(observed_mV, applied_mV, rtol=1e-6, atol=1e-9):
        raise RuntimeError("Brian2 did not retain requested plastic KC->MBON weights")

    return {
        "enabled": True,
        "model": "terminal-reward-gated-KC-MBON-coactivity-v1",
        "source": source,
        "character": character,
        "candidate_edges": int(len(candidates)),
        "candidate_sha256": candidate_sha,
        "config_sha256": config_sha,
        "state_sha256": state_sha,
        "generation": int(state.generation),
        "matches": int(state.matches),
        "updates": int(state.updates),
        "multiplier_min": float(state.multipliers.min()),
        "multiplier_max": float(state.multipliers.max()),
        "multiplier_mean": float(state.multipliers.mean()),
        "topology_changed": False,
        "sign_changed": False,
    }
