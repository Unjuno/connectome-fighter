"""Extract existing MaleCNS KC->MBON synapses for later reward-gated plasticity.

No weights are changed here. The output is an auditable index into the strict
MaleCNS->Shiu connectivity table. The initial plastic subset is intentionally
narrow because adult Drosophila learning literature directly supports
DAN-gated plasticity at Kenyon-cell-to-MBON synapses; applying reward updates to
all CNS edges would be a much stronger and poorly justified assumption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--connectivity", type=Path, required=True)
    p.add_argument("--adapter-manifest", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()

    meta = pd.read_parquet(args.metadata)
    required = {"bodyId", "Shiu_Index", "class", "type", "resolved_nt", "shiu_sign"}
    if not required.issubset(meta.columns):
        raise ValueError(f"Metadata missing columns: {required - set(meta.columns)}")
    if meta["Shiu_Index"].duplicated().any():
        raise ValueError("Shiu_Index must be unique")
    meta = meta.sort_values("Shiu_Index").reset_index(drop=True)
    if not np.array_equal(meta["Shiu_Index"].to_numpy(), np.arange(len(meta))):
        raise ValueError("Shiu_Index must form a dense 0..N-1 index")

    classes = meta["class"].astype("string").fillna("").to_numpy()
    kc_mask = classes == "Kenyon_Cell"
    mbon_mask = classes == "MBON"
    dan_mask = classes == "DAN"
    kc_indices = set(np.flatnonzero(kc_mask).tolist())
    mbon_indices = set(np.flatnonzero(mbon_mask).tolist())
    dan_indices = set(np.flatnonzero(dan_mask).tolist())
    if not kc_indices or not mbon_indices or not dan_indices:
        raise ValueError("Expected Kenyon_Cell, MBON and DAN classes in canonical metadata")

    parquet = pq.ParquetFile(args.connectivity)
    rows: list[dict] = []
    dan_to_kc = 0
    dan_to_mbon = 0
    kc_to_dan = 0
    global_row = 0
    for batch in parquet.iter_batches(batch_size=250_000):
        table = pa.Table.from_batches([batch])
        pre = table["Presynaptic_Index"].to_numpy()
        post = table["Postsynaptic_Index"].to_numpy()
        signed = table["Excitatory x Connectivity"].to_numpy()
        raw = table["MaleCNS_Weight"].to_numpy()

        is_kc_pre = np.isin(pre, list(kc_indices))
        is_mbon_post = np.isin(post, list(mbon_indices))
        selected = np.flatnonzero(is_kc_pre & is_mbon_post)
        for local in selected.tolist():
            pi, po = int(pre[local]), int(post[local])
            pre_meta, post_meta = meta.iloc[pi], meta.iloc[po]
            rows.append({
                "synapse_index": int(global_row + local),
                "pre_index": pi,
                "post_index": po,
                "body_pre": int(pre_meta["bodyId"]),
                "body_post": int(post_meta["bodyId"]),
                "type_pre": None if pd.isna(pre_meta["type"]) else str(pre_meta["type"]),
                "type_post": None if pd.isna(post_meta["type"]) else str(post_meta["type"]),
                "resolved_nt_pre": str(pre_meta["resolved_nt"]),
                "sign": int(np.sign(signed[local])),
                "base_signed_connectivity": int(signed[local]),
                "base_malecns_weight": int(raw[local]),
            })

        dan_to_kc += int((np.isin(pre, list(dan_indices)) & np.isin(post, list(kc_indices))).sum())
        dan_to_mbon += int((np.isin(pre, list(dan_indices)) & np.isin(post, list(mbon_indices))).sum())
        kc_to_dan += int((np.isin(pre, list(kc_indices)) & np.isin(post, list(dan_indices))).sum())
        global_row += len(pre)

    candidates = pd.DataFrame(rows)
    if candidates.empty:
        raise RuntimeError("No real KC->MBON edges found")
    if candidates["synapse_index"].duplicated().any():
        raise RuntimeError("Duplicate synapse index in plasticity candidates")
    # Kenyon cells in this strict substrate should be cholinergic/excitatory.
    # Do not silently accept mixed-sign candidates because later magnitude-only
    # plasticity must preserve the anatomical/transmitter sign.
    if not (candidates["sign"] == 1).all():
        bad = candidates.loc[candidates["sign"] != 1].head(10).to_dict("records")
        raise RuntimeError(f"Unexpected non-excitatory KC->MBON candidates: {bad}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = args.out_dir / "kc_mbon_candidates.parquet"
    candidates.to_parquet(candidate_path, index=False, compression="zstd")
    manifest_src = json.loads(args.adapter_manifest.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": 1,
        "plasticity_subset": "existing-Kenyon_Cell-to-MBON-edges-v1",
        "dataset": manifest_src["dataset"],
        "adapter": manifest_src["adapter"],
        "adapter_manifest_sha256": sha256(args.adapter_manifest),
        "metadata_sha256": sha256(args.metadata),
        "connectivity_sha256": sha256(args.connectivity),
        "counts": {
            "kenyon_cells": int(kc_mask.sum()),
            "mbons": int(mbon_mask.sum()),
            "dans": int(dan_mask.sum()),
            "kc_to_mbon_edges": int(len(candidates)),
            "unique_kc_in_candidates": int(candidates["pre_index"].nunique()),
            "unique_mbon_in_candidates": int(candidates["post_index"].nunique()),
            "dan_to_kc_edges": int(dan_to_kc),
            "dan_to_mbon_edges": int(dan_to_mbon),
            "kc_to_dan_edges": int(kc_to_dan),
        },
        "base_weight_summary": {
            "min": int(candidates["base_malecns_weight"].min()),
            "median": float(candidates["base_malecns_weight"].median()),
            "max": int(candidates["base_malecns_weight"].max()),
            "sum": int(candidates["base_malecns_weight"].sum()),
        },
        "candidate_file": candidate_path.name,
        "candidate_file_sha256": sha256(candidate_path),
        "invariants": {
            "topology_changes_allowed": False,
            "sign_changes_allowed": False,
            "candidate_sign": 1,
            "learning_not_applied_by_this_step": True,
        },
        "interpretation_boundary": (
            "This file identifies anatomically existing candidate synapses only. "
            "A reward-dependent update rule is a separately versioned project model extension."
        ),
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
