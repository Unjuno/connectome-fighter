"""Apply one terminal game reward to a character's real KC->MBON synapses.

Eligibility is computed from logged real MaleCNS body-ID spike counts per
FightingICE decision window. For every anatomically existing KC->MBON candidate
edge, decision co-activity contributes `min(pre_count*post_count, cap)` to an
eligibility trace that decays across decisions. The terminal scalar reward then
modulates only the candidate edge magnitudes; topology and sign are immutable.

This is an explicitly project-defined reward-plasticity extension. It is not a
claim that a Drosophila game reward is literally represented by one endogenous
DAN signal.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from connectome_fighter.reward_plasticity import (
    RewardPlasticityConfig,
    apply_terminal_reward,
    initialize_state,
    load_state,
    save_state,
    sha256_file,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--character", required=True)
    p.add_argument("--candidates", type=Path, required=True)
    p.add_argument("--spikes", type=Path, required=True)
    p.add_argument("--reward", type=float, choices=[-1.0, 0.0, 1.0], required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--out-summary", type=Path, required=True)
    p.add_argument("--learning-rate", type=float, default=0.02)
    p.add_argument("--eligibility-decay", type=float, default=0.9)
    p.add_argument("--pair-count-cap", type=float, default=25.0)
    p.add_argument("--multiplier-min", type=float, default=0.5)
    p.add_argument("--multiplier-max", type=float, default=1.5)
    args = p.parse_args()

    config = RewardPlasticityConfig(
        learning_rate=args.learning_rate,
        eligibility_decay_per_decision=args.eligibility_decay,
        pair_count_cap=args.pair_count_cap,
        multiplier_min=args.multiplier_min,
        multiplier_max=args.multiplier_max,
    )
    config.validate()
    candidates = pd.read_parquet(args.candidates)
    required = {"synapse_index", "body_pre", "body_post", "sign"}
    if not required.issubset(candidates.columns) or candidates.empty:
        raise ValueError("invalid KC->MBON candidate table")
    if not (candidates["sign"] == 1).all():
        raise ValueError("candidate sign invariant violated")
    candidate_sha = sha256_file(args.candidates)

    if args.state.is_file():
        state = load_state(
            args.state,
            expected_character=args.character,
            n_candidates=len(candidates),
            expected_candidate_sha256=candidate_sha,
            expected_config_sha256=config.fingerprint(),
        )
    else:
        state = initialize_state(
            character=args.character,
            n_candidates=len(candidates),
            candidate_sha256=candidate_sha,
            config=config,
        )

    spikes = pd.read_parquet(args.spikes)
    spike_required = {"decision_index", "body_id"}
    if not spike_required.issubset(spikes.columns):
        raise ValueError("spike log lacks decision_index/body_id")
    if spikes.empty:
        eligibility = np.zeros(len(candidates), dtype=np.float64)
        decisions = []
    else:
        spikes["decision_index"] = spikes["decision_index"].astype(int)
        counts = spikes.groupby(["decision_index", "body_id"]).size()
        decisions = sorted(spikes["decision_index"].unique().tolist())
        pre_bodies = candidates["body_pre"].to_numpy(dtype=np.int64)
        post_bodies = candidates["body_post"].to_numpy(dtype=np.int64)
        eligibility = np.zeros(len(candidates), dtype=np.float64)
        for decision in decisions:
            if decision != decisions[0]:
                eligibility *= config.eligibility_decay_per_decision
            decision_counts = counts.loc[decision] if decision in counts.index.get_level_values(0) else pd.Series(dtype=int)
            # Reindex vectorization avoids O(edges*spikes) pair loops.
            pre_counts = decision_counts.reindex(pre_bodies, fill_value=0).to_numpy(dtype=np.float64)
            post_counts = decision_counts.reindex(post_bodies, fill_value=0).to_numpy(dtype=np.float64)
            coactivity = np.minimum(pre_counts * post_counts, config.pair_count_cap)
            eligibility += coactivity

    before_generation = state.generation
    metrics = apply_terminal_reward(state, eligibility, float(args.reward), config)
    meta = save_state(args.state, state)
    summary = {
        "status": "PASS",
        "plasticity_model": "terminal-reward-gated-KC-MBON-coactivity-v1",
        "character": args.character,
        "reward": float(args.reward),
        "candidate_edges": int(len(candidates)),
        "decision_windows": int(len(decisions)),
        "generation_before": int(before_generation),
        "generation_after": int(state.generation),
        "config": {
            "learning_rate": config.learning_rate,
            "eligibility_decay_per_decision": config.eligibility_decay_per_decision,
            "pair_count_cap": config.pair_count_cap,
            "multiplier_min": config.multiplier_min,
            "multiplier_max": config.multiplier_max,
            "normalization_percentile": config.normalization_percentile,
            "config_sha256": config.fingerprint(),
        },
        "metrics": metrics,
        "state": meta,
        "invariants": {
            "topology_changed": False,
            "transmitter_sign_changed": False,
            "plastic_edges_are_real_KC_to_MBON_edges": True,
        },
        "interpretation_boundary": (
            "The terminal game reward is an external modulatory signal. The update is "
            "dopamine-inspired and anatomically constrained, not an identified endogenous "
            "FightingICE reinforcement circuit in Drosophila."
        ),
    }
    args.out_summary.parent.mkdir(parents=True, exist_ok=True)
    args.out_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
