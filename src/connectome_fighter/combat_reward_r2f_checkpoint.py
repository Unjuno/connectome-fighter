"""Explicit, hash-audited R2e -> R2f research lineage fork.

This module cannot edit a source checkpoint, mutate canonical deployment, or
silently change topology, signs, optimizer, or any plasticity hyperparameters.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from connectome_fighter.valence_plasticity import (
    ValencePlasticityConfig, load_state, save_state, sha256_file,
)
from connectome_fighter.combat_reward_r2f import REWARD_ID


def fork_r2e_to_r2f(
    source: Path, destination: Path,
    old: ValencePlasticityConfig, new: ValencePlasticityConfig
) -> dict:
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError("research destination must be new and different from the canonical checkpoint")
    if (old.reward_id != "R2e-combat-v1" or new.reward_id != REWARD_ID
            or replace(new, reward_id=old.reward_id) != old):
        raise ValueError("only the reward ID may differ in an R2e-to-R2f fork")
    old.validate()
    new.validate()
    meta_path = source.with_suffix(source.suffix + ".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    source_sha, source_meta_sha = sha256_file(source), sha256_file(meta_path)
    state = load_state(
        source,
        expected_character=meta["character"],
        n_candidates=int(meta["n_candidates"]),
        expected_candidate_sha256=meta["candidate_sha256"],
        config=old,
    )
    original = state.multipliers.copy()
    counts = (state.generation, state.matches, state.update_events)
    state.config_sha256 = new.fingerprint()
    new_meta = save_state(destination, state, new)
    restored = load_state(
        destination,
        expected_character=meta["character"],
        n_candidates=len(original),
        expected_candidate_sha256=meta["candidate_sha256"],
        config=new,
    )
    if not np.array_equal(original, restored.multipliers):
        raise RuntimeError("checkpoint multipliers were changed by reward fork")
    if (restored.generation, restored.matches, restored.update_events) != counts:
        raise RuntimeError("checkpoint counters were changed by reward fork")
    if sha256_file(source) != source_sha or sha256_file(meta_path) != source_meta_sha:
        raise RuntimeError("canonical checkpoint bytes changed")
    receipt = {
        "kind": "explicit-research-only-r2e-to-r2f-fork",
        "from_reward": old.reward_id,
        "to_reward": new.reward_id,
        "source_checkpoint_sha256": source_sha,
        "source_metadata_sha256": source_meta_sha,
        "source_generation": meta["generation"],
        "source_config_sha256": old.fingerprint(),
        "new_config_sha256": new.fingerprint(),
        "weights_identical": True,
        "generation_unchanged": True,
        "automatic_promotion": False,
        "new_state": new_meta,
    }
    destination.with_suffix(destination.suffix + ".fork.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt
