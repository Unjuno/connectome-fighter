"""Convert official MaleCNS v1.0 flat-connectome data into Shiu model inputs.

This script changes DATA REPRESENTATION only. It does not implement neural
dynamics. The output `completeness.csv` and `connectivity.parquet` are consumed
by the pinned Shiu et al. `model.py:create_model()` reference implementation.

Conservative rules for the initial canonical gate:
- neuron set mirrors the MaleCNS paper repository quantification criterion:
  non-null superclass and superclass does not contain `tbc`;
- transmitter is resolved from released fields without guessing:
  consensus_nt -> predicted_nt(conf>=0.5) -> celltype_predicted_nt(conf>=0.5);
- bodies with unresolved transmitter are excluded;
- histamine is excluded in `strict-shiu` mode because the Shiu publication's
  sign convention explicitly covers ACh/GABA/Glu/DA/Oct/Ser but not histamine;
- connection strength threshold defaults to >=5, matching the MaleCNS paper
  repository's quantified network example. The threshold is recorded and is a
  runtime approximation, not a claim about biological absence of weak edges.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

UNKNOWN = {"", "<na>", "unclear", "unknown", "none", "nan"}
SHIU_SIGN = {
    "acetylcholine": 1,
    "dopamine": 1,
    "octopamine": 1,
    "serotonin": 1,
    "gaba": -1,
    "glutamate": -1,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm_nt(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower()


def resolve_nt(row: pd.Series) -> tuple[str, str]:
    consensus = norm_nt(row.get("consensus_nt"))
    if consensus not in UNKNOWN:
        return consensus, "consensus_nt"

    predicted = norm_nt(row.get("predicted_nt"))
    pred_conf = pd.to_numeric(pd.Series([row.get("predicted_nt_confidence")]), errors="coerce").iloc[0]
    if predicted not in UNKNOWN and pd.notna(pred_conf) and float(pred_conf) >= 0.5:
        return predicted, "predicted_nt_conf>=0.5"

    cell = norm_nt(row.get("celltype_predicted_nt"))
    cell_conf = pd.to_numeric(
        pd.Series([row.get("celltype_predicted_nt_confidence")]), errors="coerce"
    ).iloc[0]
    if cell not in UNKNOWN and pd.notna(cell_conf) and float(cell_conf) >= 0.5:
        return cell, "celltype_predicted_nt_conf>=0.5"
    return "", "unresolved"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--neurotransmitters", type=Path, required=True)
    p.add_argument("--connectivity", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--min-weight", type=int, default=5)
    p.add_argument("--histamine-mode", choices=["strict-shiu", "inhibitory"], default="strict-shiu")
    p.add_argument("--shiu-reference-commit", required=True)
    args = p.parse_args()
    if args.min_weight <= 0:
        p.error("--min-weight must be positive")

    args.out.mkdir(parents=True, exist_ok=True)
    ann = pd.read_feather(args.annotations)
    nt = pd.read_feather(args.neurotransmitters)
    required_ann = {"bodyId", "superclass"}
    if not required_ann.issubset(ann.columns):
        raise ValueError(f"Missing annotation columns: {required_ann - set(ann.columns)}")
    if "body" not in nt.columns:
        raise ValueError("Neurotransmitter table must contain `body`")

    superclass = ann["superclass"].astype("string")
    valid = superclass.notna() & ~superclass.str.contains("tbc", case=False, na=False)
    candidate = ann.loc[valid].copy()

    nt_columns = [
        c for c in [
            "body", "consensus_nt", "predicted_nt", "predicted_nt_confidence",
            "celltype_predicted_nt", "celltype_predicted_nt_confidence",
        ] if c in nt.columns
    ]
    candidate = candidate.merge(
        nt[nt_columns].drop_duplicates(subset=["body"]),
        left_on="bodyId", right_on="body", how="left", validate="one_to_one",
    )
    resolved = candidate.apply(resolve_nt, axis=1, result_type="expand")
    candidate["resolved_nt"] = resolved[0]
    candidate["nt_resolution_source"] = resolved[1]

    unresolved_mask = candidate["resolved_nt"].eq("")
    histamine_mask = candidate["resolved_nt"].eq("histamine")
    sign_map = dict(SHIU_SIGN)
    if args.histamine_mode == "inhibitory":
        sign_map["histamine"] = -1
    supported_mask = candidate["resolved_nt"].isin(sign_map)
    included = candidate.loc[supported_mask].copy()
    included["shiu_sign"] = included["resolved_nt"].map(sign_map).astype(np.int8)
    included = included.sort_values("bodyId", kind="stable").reset_index(drop=True)
    included["Shiu_Index"] = np.arange(len(included), dtype=np.int64)

    if included.empty or included["bodyId"].duplicated().any():
        raise ValueError("Invalid included MaleCNS neuron set")
    body_ids = included["bodyId"].to_numpy(dtype=np.int64, copy=True)
    signs = included["shiu_sign"].to_numpy(dtype=np.int8, copy=True)

    completeness_columns = [
        c for c in [
            "bodyId", "Shiu_Index", "superclass", "class", "subclass", "type",
            "instance", "somaSide", "somaNeuromere", "rootSide", "status",
            "statusLabel", "resolved_nt", "nt_resolution_source", "shiu_sign",
        ] if c in included.columns
    ]
    completeness = included[completeness_columns].set_index("bodyId", drop=True)
    completeness_path = args.out / "completeness.csv"
    completeness.to_csv(completeness_path)

    metadata_path = args.out / "neuron_metadata.parquet"
    included[completeness_columns].to_parquet(metadata_path, index=False, compression="zstd")

    connectivity_path = args.out / "connectivity.parquet"
    schema = pa.schema([
        ("Presynaptic_Index", pa.int64()),
        ("Postsynaptic_Index", pa.int64()),
        ("Excitatory x Connectivity", pa.int64()),
        ("MaleCNS_Weight", pa.int64()),
    ])
    writer = pq.ParquetWriter(connectivity_path, schema, compression="zstd")
    source = pa.memory_map(str(args.connectivity), "r")
    reader = ipc.open_file(source)
    edge_count = 0
    excitatory_edges = 0
    inhibitory_edges = 0
    weak_edges_skipped = 0
    outside_body_set_skipped = 0
    total_input_edges = 0
    try:
        for batch_index in range(reader.num_record_batches):
            batch = reader.get_batch(batch_index)
            pre = batch.column(batch.schema.get_field_index("body_pre")).to_numpy(zero_copy_only=False)
            post = batch.column(batch.schema.get_field_index("body_post")).to_numpy(zero_copy_only=False)
            weight = batch.column(batch.schema.get_field_index("weight")).to_numpy(zero_copy_only=False)
            total_input_edges += len(weight)

            weight_mask = weight >= args.min_weight
            weak_edges_skipped += int((~weight_mask).sum())
            if not weight_mask.any():
                continue
            pre = pre[weight_mask].astype(np.int64, copy=False)
            post = post[weight_mask].astype(np.int64, copy=False)
            weight = weight[weight_mask].astype(np.int64, copy=False)

            pre_idx = np.searchsorted(body_ids, pre)
            post_idx = np.searchsorted(body_ids, post)
            valid_pre = pre_idx < len(body_ids)
            valid_post = post_idx < len(body_ids)
            pre_match = np.zeros_like(valid_pre, dtype=bool)
            post_match = np.zeros_like(valid_post, dtype=bool)
            pre_match[valid_pre] = body_ids[pre_idx[valid_pre]] == pre[valid_pre]
            post_match[valid_post] = body_ids[post_idx[valid_post]] == post[valid_post]
            keep = pre_match & post_match
            outside_body_set_skipped += int((~keep).sum())
            if not keep.any():
                continue

            pre_idx = pre_idx[keep].astype(np.int64, copy=False)
            post_idx = post_idx[keep].astype(np.int64, copy=False)
            raw_weight = weight[keep].astype(np.int64, copy=False)
            signed = raw_weight * signs[pre_idx].astype(np.int64)
            if np.any(signed == 0):
                raise AssertionError("Included edge unexpectedly has zero sign")

            excitatory_edges += int((signed > 0).sum())
            inhibitory_edges += int((signed < 0).sum())
            edge_count += len(signed)
            writer.write_table(pa.table({
                "Presynaptic_Index": pre_idx,
                "Postsynaptic_Index": post_idx,
                "Excitatory x Connectivity": signed,
                "MaleCNS_Weight": raw_weight,
            }, schema=schema))
    finally:
        writer.close()

    if edge_count == 0:
        raise RuntimeError("No MaleCNS edges survived canonical filtering")

    source_counts = included["nt_resolution_source"].value_counts().to_dict()
    nt_counts = included["resolved_nt"].value_counts().to_dict()
    superclass_counts = included["superclass"].astype("string").value_counts().to_dict()
    manifest = {
        "schema_version": 1,
        "dataset": "male-cns:v1.0",
        "adapter": "malecns-to-shiu-reference-v1",
        "shiu_reference_commit": args.shiu_reference_commit,
        "selection_rule": "superclass non-null and name does not contain 'tbc'",
        "transmitter_resolution": (
            "consensus_nt -> predicted_nt(conf>=0.5) -> "
            "celltype_predicted_nt(conf>=0.5); unresolved excluded"
        ),
        "histamine_mode": args.histamine_mode,
        "min_connection_weight": args.min_weight,
        "min_connection_weight_basis": (
            "Initial runtime threshold follows the MaleCNS paper repository's "
            "quantify-neuron-connections example; weak edges remain in source data."
        ),
        "sign_convention": {
            "excitatory": [k for k, v in sign_map.items() if v > 0],
            "inhibitory": [k for k, v in sign_map.items() if v < 0],
            "source": "Shiu et al. convention for ACh/GABA/Glu/DA/Oct/Ser; histamine only if explicitly enabled",
        },
        "counts": {
            "annotation_rows": int(len(ann)),
            "official_style_candidates": int(len(candidate)),
            "included_neurons": int(len(included)),
            "excluded_unresolved_nt": int(unresolved_mask.sum()),
            "candidate_histamine": int(histamine_mask.sum()),
            "excluded_unsupported_or_unresolved": int((~supported_mask).sum()),
            "source_edges": int(total_input_edges),
            "runtime_edges": int(edge_count),
            "runtime_excitatory_edges": int(excitatory_edges),
            "runtime_inhibitory_edges": int(inhibitory_edges),
            "weak_edges_skipped_before_body_filter": int(weak_edges_skipped),
            "strong_edges_outside_included_body_set": int(outside_body_set_skipped),
        },
        "included_nt_counts": {str(k): int(v) for k, v in nt_counts.items()},
        "nt_resolution_source_counts": {str(k): int(v) for k, v in source_counts.items()},
        "included_superclass_counts": {str(k): int(v) for k, v in superclass_counts.items()},
        "source_hashes": {
            "annotations_sha256": sha256(args.annotations),
            "neurotransmitters_sha256": sha256(args.neurotransmitters),
            "connectivity_sha256": sha256(args.connectivity),
        },
        "output_hashes": {
            "completeness_sha256": sha256(completeness_path),
            "neuron_metadata_sha256": sha256(metadata_path),
            "connectivity_sha256": sha256(connectivity_path),
        },
        "interpretation_boundary": (
            "These files adapt MaleCNS structure to the published Shiu model's input schema. "
            "The Shiu dynamics themselves are loaded from the pinned upstream reference code."
        ),
    }
    manifest_path = args.out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
