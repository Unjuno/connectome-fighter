"""Create a fixed, fully logged FightingICE <-> MaleCNS interface.

This file deliberately contains no trainable neural network. It assigns the
18 normalized game features to real MaleCNS sensory bodies using positive/
negative half-wave Poisson-rate channels, and partitions real descending/motor
bodies into seven active action groups. NEUTRAL is chosen when no output group
crosses the configured spike-count threshold.

The assignment is artificial and versioned. The biological facts are only the
body IDs and their annotations; game semantics are never presented as native
Drosophila sensory/motor semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

import pandas as pd

FEATURES = [
    "own_hp", "opp_hp", "own_energy", "opp_energy",
    "signed_dx", "dy", "own_signed_vx", "own_vy",
    "opp_signed_vx", "opp_vy", "own_remaining_frame", "opp_remaining_frame",
    "own_control", "opp_control", "own_y", "opp_y",
    "same_facing", "normalized_frame",
]
ACTIVE_ACTIONS = ["FORWARD", "BACKWARD", "UP", "DOWN", "A", "B", "C"]
INPUT_SUPERCLASSES = {
    "cb_sensory", "vnc_sensory", "sensory_ascending", "sensory_descending",
}
OUTPUT_SUPERCLASSES = {
    "descending_neuron", "vnc_motor", "cb_motor", "vnc_efferent",
    "efferent_descending",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=20260911)
    p.add_argument("--input-bodies-per-polarity-feature", type=int, default=16)
    p.add_argument("--max-poisson-rate-hz", type=float, default=150.0)
    p.add_argument("--decision-window-ms", type=float, default=20.0)
    p.add_argument("--neutral-min-spikes", type=int, default=1)
    args = p.parse_args()
    if args.input_bodies_per_polarity_feature <= 0:
        p.error("input bodies per feature/polarity must be positive")
    if args.max_poisson_rate_hz <= 0 or args.decision_window_ms <= 0:
        p.error("rate/window must be positive")
    if args.neutral_min_spikes < 0:
        p.error("neutral threshold must be non-negative")

    meta = pd.read_parquet(args.metadata)
    required = {"bodyId", "Shiu_Index", "superclass", "resolved_nt", "shiu_sign"}
    if not required.issubset(meta.columns):
        raise ValueError(f"Metadata is missing required columns: {required - set(meta.columns)}")
    if meta["bodyId"].duplicated().any() or meta["Shiu_Index"].duplicated().any():
        raise ValueError("Metadata body/index identifiers must be unique")

    input_pool = meta.loc[meta["superclass"].isin(INPUT_SUPERCLASSES)].copy()
    output_pool = meta.loc[meta["superclass"].isin(OUTPUT_SUPERCLASSES)].copy()
    output_pool = output_pool.loc[~output_pool["bodyId"].isin(input_pool["bodyId"])]
    need = len(FEATURES) * 2 * args.input_bodies_per_polarity_feature
    if len(input_pool) < need:
        raise ValueError(f"Need {need} sensory bodies, found {len(input_pool)}")
    if len(output_pool) < len(ACTIVE_ACTIONS):
        raise ValueError("Not enough descending/motor bodies for action groups")

    rng = random.Random(args.seed)
    input_rows = input_pool.sort_values("bodyId").to_dict("records")
    rng.shuffle(input_rows)
    input_rows = input_rows[:need]
    channels = []
    cursor = 0
    for feature_index, feature_name in enumerate(FEATURES):
        for polarity in (1, -1):
            selected = input_rows[cursor:cursor + args.input_bodies_per_polarity_feature]
            cursor += args.input_bodies_per_polarity_feature
            channels.append({
                "feature_index": feature_index,
                "feature_name": feature_name,
                "polarity": polarity,
                "body_ids": [int(x["bodyId"]) for x in selected],
                "shiu_indices": [int(x["Shiu_Index"]) for x in selected],
                "superclasses": sorted({str(x["superclass"]) for x in selected}),
                "rate_rule": "max(0, polarity * clipped_feature) * max_poisson_rate_hz",
            })

    output_rows = output_pool.sort_values("bodyId").to_dict("records")
    rng.shuffle(output_rows)
    groups = {name: [] for name in ACTIVE_ACTIONS}
    for i, row in enumerate(output_rows):
        groups[ACTIVE_ACTIONS[i % len(ACTIVE_ACTIONS)]].append(row)
    action_groups = {
        name: {
            "body_ids": [int(x["bodyId"]) for x in rows],
            "shiu_indices": [int(x["Shiu_Index"]) for x in rows],
            "superclass_counts": {
                str(k): int(v)
                for k, v in pd.Series([x["superclass"] for x in rows], dtype="string").value_counts().to_dict().items()
            },
        }
        for name, rows in groups.items()
    }

    structural = json.loads(args.manifest.read_text(encoding="utf-8"))
    payload = {
        "schema_version": 1,
        "interface_id": "fightingice-malecns-poisson-spike-v1",
        "dataset": structural["dataset"],
        "adapter": structural["adapter"],
        "structural_manifest_sha256": sha256(args.manifest),
        "neuron_metadata_sha256": sha256(args.metadata),
        "assignment_seed": args.seed,
        "observation_features": FEATURES,
        "input": {
            "source_superclasses": sorted(INPUT_SUPERCLASSES),
            "candidate_bodies": int(len(input_pool)),
            "bodies_per_feature_polarity": args.input_bodies_per_polarity_feature,
            "max_poisson_rate_hz": args.max_poisson_rate_hz,
            "poisson_weight_rule": "Shiu w_syn * f_poi, identical event amplitude to published activation helper",
            "feature_clip_for_rate": [-1.0, 1.0],
            "channels": channels,
        },
        "decision": {
            "window_ms": args.decision_window_ms,
            "rule": "count spikes in each action body group during decision window",
            "active_actions": ACTIVE_ACTIONS,
            "neutral_rule": (
                f"NEUTRAL if max group spike count < {args.neutral_min_spikes}; "
                "otherwise choose max-count group; deterministic action-order tie break"
            ),
            "neutral_min_spikes": args.neutral_min_spikes,
        },
        "output": {
            "source_superclasses": sorted(OUTPUT_SUPERCLASSES),
            "candidate_bodies": int(len(output_pool)),
            "groups": action_groups,
        },
        "interpretation_boundary": (
            "MaleCNS body IDs and annotations are biological data. Feature-to-sensory and "
            "output-to-game-action assignments are artificial interface choices and are "
            "not claimed to be native fly sensorimotor semantics."
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["interface_sha256"] = hashlib.sha256(encoded).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "interface_sha256": payload["interface_sha256"],
        "input_candidates": len(input_pool),
        "selected_input_bodies": need,
        "output_candidates": len(output_pool),
        "action_group_sizes": {k: len(v["body_ids"]) for k, v in action_groups.items()},
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
