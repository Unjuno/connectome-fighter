"""Materialize one character's KC->MBON plasticity into Shiu input tables.

The pinned Shiu dynamics code remains untouched. This step rewrites only the
`Excitatory x Connectivity` values of candidate rows in a temporary per-character
connectivity parquet, preserving row order, pre/post indices and sign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from connectome_fighter.reward_plasticity import (
    RewardPlasticityConfig, initialize_state, load_state, sha256_file,
)


def hardlink_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-adapter", type=Path, required=True)
    p.add_argument("--candidates", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--character", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    config = RewardPlasticityConfig()
    candidates = pd.read_parquet(args.candidates).sort_values("synapse_index").reset_index(drop=True)
    if candidates.empty or not (candidates["sign"] == 1).all():
        raise ValueError("invalid KC->MBON candidate set")
    candidate_sha = sha256_file(args.candidates)
    if args.state.is_file():
        state = load_state(
            args.state,
            expected_character=args.character,
            n_candidates=len(candidates),
            expected_candidate_sha256=candidate_sha,
            expected_config_sha256=config.fingerprint(),
        )
        state_source = "checkpoint"
        state_sha = sha256_file(args.state)
    else:
        state = initialize_state(
            character=args.character,
            n_candidates=len(candidates),
            candidate_sha256=candidate_sha,
            config=config,
        )
        state_source = "unity-initial-state"
        state_sha = hashlib.sha256(state.multipliers.tobytes()).hexdigest()

    base_manifest = json.loads((args.base_adapter / "manifest.json").read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for filename in ["completeness.csv", "neuron_metadata.parquet"]:
        dst = args.out / filename
        if dst.exists():
            dst.unlink()
        hardlink_or_copy(args.base_adapter / filename, dst)

    candidate_index = candidates["synapse_index"].to_numpy(dtype=np.int64)
    multipliers = state.multipliers.astype(np.float64)
    src = pq.ParquetFile(args.base_adapter / "connectivity.parquet")
    dst_path = args.out / "connectivity.parquet"
    schema = pa.schema([
        ("Presynaptic_Index", pa.int64()),
        ("Postsynaptic_Index", pa.int64()),
        ("Excitatory x Connectivity", pa.float64()),
        ("MaleCNS_Weight", pa.int64()),
    ])
    writer = pq.ParquetWriter(dst_path, schema, compression="zstd")
    offset = 0
    changed_rows = 0
    try:
        for batch in src.iter_batches(batch_size=250_000):
            t = pa.Table.from_batches([batch])
            pre = t["Presynaptic_Index"].to_numpy().astype(np.int64, copy=False)
            post = t["Postsynaptic_Index"].to_numpy().astype(np.int64, copy=False)
            signed = t["Excitatory x Connectivity"].to_numpy().astype(np.float64, copy=True)
            raw = t["MaleCNS_Weight"].to_numpy().astype(np.int64, copy=False)
            end = offset + len(signed)
            lo = np.searchsorted(candidate_index, offset, side="left")
            hi = np.searchsorted(candidate_index, end, side="left")
            if hi > lo:
                global_idx = candidate_index[lo:hi]
                local_idx = global_idx - offset
                expected_pre = candidates["pre_index"].to_numpy(dtype=np.int64)[lo:hi]
                expected_post = candidates["post_index"].to_numpy(dtype=np.int64)[lo:hi]
                if not np.array_equal(pre[local_idx], expected_pre) or not np.array_equal(post[local_idx], expected_post):
                    raise ValueError("candidate row identity no longer matches base adapter ordering")
                if np.any(signed[local_idx] <= 0):
                    raise ValueError("candidate base sign is no longer positive")
                signed[local_idx] *= multipliers[lo:hi]
                if np.any(signed[local_idx] <= 0):
                    raise ValueError("plasticity would change candidate sign")
                changed_rows += len(local_idx)
            writer.write_table(pa.table({
                "Presynaptic_Index": pre,
                "Postsynaptic_Index": post,
                "Excitatory x Connectivity": signed,
                "MaleCNS_Weight": raw,
            }, schema=schema))
            offset = end
    finally:
        writer.close()
    if changed_rows != len(candidates):
        raise RuntimeError(f"materialized {changed_rows} candidate rows, expected {len(candidates)}")

    manifest = dict(base_manifest)
    manifest["adapter"] = "malecns-to-shiu-reference-v1+KC-MBON-plasticity-v1"
    manifest["base_adapter"] = base_manifest["adapter"]
    manifest["plasticity"] = {
        "model": "terminal-reward-gated-KC-MBON-coactivity-v1",
        "character": args.character,
        "state_source": state_source,
        "generation": int(state.generation),
        "matches": int(state.matches),
        "updates": int(state.updates),
        "candidate_edges": int(len(candidates)),
        "candidate_sha256": candidate_sha,
        "config_sha256": config.fingerprint(),
        "state_sha256": state_sha,
        "multiplier_min": float(state.multipliers.min()),
        "multiplier_max": float(state.multipliers.max()),
        "multiplier_mean": float(state.multipliers.mean()),
        "topology_changed": False,
        "sign_changed": False,
    }
    manifest["output_hashes"] = dict(base_manifest["output_hashes"])
    manifest["output_hashes"]["connectivity_sha256"] = sha256_file(dst_path)
    manifest["interpretation_boundary"] = (
        "Per-character reward plasticity modifies magnitudes of anatomically existing KC->MBON rows only. "
        "The pinned upstream Shiu model.py remains the executable dynamics implementation."
    )
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status":"PASS","character":args.character,
                      "generation":state.generation,"candidate_edges":len(candidates),
                      "connectivity_sha256":manifest["output_hashes"]["connectivity_sha256"]},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
