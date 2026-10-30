#!/usr/bin/env python3
"""Deterministically attenuate ONE complete R2f KC-MBON proposal.

No synthetic game data and no invented reward: both inputs are SHA-verified
checkpoints created by real MaleCNS/FightingICE training. This is a bounded
proposal-size intervention, not a changed plasticity target or an acceptance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np

from connectome_fighter.combat_checkpoint import config_from_json
from connectome_fighter.valence_plasticity import load_state, save_state, sha256_file

SCHEME = "r2f-trust-region-backtrack-v1"
SCALE = 0.25
REWARD = "R2e-combat-v1"
CREDIT = "R2f-credit-balanced-v1"


def make_backtracked_checkpoint(parent: Path, proposed: Path, destination: Path,
                                plasticity_config: Path, credit_config: Path) -> dict:
    parent = Path(parent)
    proposed = Path(proposed)
    destination = Path(destination)
    if len({parent.resolve(), proposed.resolve(), destination.resolve()}) != 3:
        raise ValueError("parent, proposed and backtracked paths must differ")
    if destination.exists() or destination.with_suffix(".npz.json").exists():
        raise ValueError("backtracking cannot overwrite existing checkpoint")
    raw = json.loads(Path(plasticity_config).read_text(encoding="utf-8"))
    cfg = config_from_json(raw)
    if cfg.reward_id != REWARD or raw["reward_config"] != REWARD:
        raise ValueError("external objective cannot change")
    credit = json.loads(Path(credit_config).read_text(encoding="utf-8"))
    from connectome_fighter.combat_reward_r2f import validate_config
    validate_config(credit)
    credit_sha = sha256_file(credit_config)

    parent_meta = json.loads(parent.with_suffix(".npz.json").read_text(encoding="utf-8"))
    proposed_meta = json.loads(proposed.with_suffix(".npz.json").read_text(encoding="utf-8"))
    if (proposed_meta.get("learning_credit_id") != CREDIT
            or proposed_meta.get("learning_credit_sha256") != credit_sha
            or proposed_meta.get("external_evaluation_reward_id") != REWARD):
        raise ValueError("proposed checkpoint learning-credit identity mismatched")
    if parent_meta.get("learning_credit_id") not in (None, CREDIT):
        raise ValueError("invalid parent learning-credit lineage")
    if parent_meta.get("learning_credit_id") == CREDIT and parent_meta.get("learning_credit_sha256") != credit_sha:
        raise ValueError("parent learning-credit byte hash mismatched")
    for key in ("character", "candidate_sha256", "n_candidates", "config_sha256", "reward_id"):
        if parent_meta.get(key) != proposed_meta.get(key):
            raise ValueError("parent and proposed identities disagree: " + key)
    if (proposed_meta["generation"] != parent_meta["generation"] + 1
            or proposed_meta["matches"] != parent_meta["matches"] + 1
            or proposed_meta["update_events"] < parent_meta["update_events"]):
        raise ValueError("proposed counters do not represent one completed game")

    common = dict(expected_character="GARNET",
                  n_candidates=int(parent_meta["n_candidates"]),
                  expected_candidate_sha256=parent_meta["candidate_sha256"], config=cfg)
    p = load_state(parent, **common)
    q = load_state(proposed, **common)
    base = p.multipliers.astype(np.float64)
    full = q.multipliers.astype(np.float64)
    if np.any(full > base + 1e-7):
        raise ValueError("proposal violates depression-only invariant")
    adjusted = (base + SCALE * (full - base)).astype(np.float32)
    if np.any(adjusted > p.multipliers + 1e-7) or np.any(adjusted < q.multipliers - 1e-7):
        raise ValueError("backtracked synapses violate monotone bounded update")
    if np.array_equal(adjusted, p.multipliers):
        raise ValueError("backtracking produced a no-op checkpoint")

    q.multipliers = adjusted
    info = save_state(destination, q, cfg)
    info.update({
        "learning_credit_id": CREDIT,
        "learning_credit_sha256": credit_sha,
        "external_evaluation_reward_id": REWARD,
        "proposal_step_scheme": SCHEME,
        "proposal_step_scale": SCALE,
        "source_proposal_sha256": sha256_file(proposed),
        "source_parent_sha256": sha256_file(parent),
    })
    destination.with_suffix(".npz.json").write_text(
        json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    loaded = load_state(destination, **common)
    if (loaded.generation != q.generation or loaded.matches != q.matches
            or not np.array_equal(loaded.multipliers, adjusted)):
        raise RuntimeError("backtracked checkpoint failed round-trip verification")
    delta = np.abs(adjusted.astype(np.float64) - base)
    return {
        "kind": SCHEME, "step_scale": SCALE,
        "parent_sha256": sha256_file(parent),
        "full_proposal_sha256": sha256_file(proposed),
        "backtracked_sha256": info["state_sha256"],
        "updated_edges": int(np.count_nonzero(delta > 1e-12)),
        "potentiated_edges": int(np.count_nonzero(adjusted > p.multipliers + 1e-7)),
        "mean_abs_multiplier_delta": float(delta.mean()),
        "max_abs_multiplier_delta": float(delta.max()),
        "learning_credit_id": CREDIT,
        "external_evaluation_reward_id": REWARD,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plasticity-config", type=Path, required=True)
    parser.add_argument("--credit-config", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    result = make_backtracked_checkpoint(args.parent, args.proposal, args.out,
                                         args.plasticity_config, args.credit_config)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
