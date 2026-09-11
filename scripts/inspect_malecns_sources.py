"""Audit pinned official MaleCNS v1.0 bulk files before any simulation.

This script does not invent a neural model. It verifies the structural source
files, records hashes/schemas, and detects the columns needed by the later
MaleCNS adapter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc

DATASET = "male-cns:v1.0"
OFFICIAL_QUANTIFICATION_CODE = "flyconnectome/2025malecns:supplemental_data/quantify-neuron-connections.ipynb"
UNKNOWN_NT = {"<na>", "unclear", "unknown", "none", "nan", ""}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def first_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    by_lower = {str(c).lower(): str(c) for c in columns}
    for candidate in candidates:
        hit = by_lower.get(candidate.lower())
        if hit is not None:
            return hit
    return None


def compact_counts(series: pd.Series, limit: int = 40) -> dict[str, int]:
    counts = series.astype("string").fillna("<NA>").value_counts(dropna=False).head(limit)
    return {str(k): int(v) for k, v in counts.items()}


def arrow_schema(path: Path) -> tuple[list[dict[str, str]], int]:
    source = pa.memory_map(str(path), "r")
    reader = ipc.open_file(source)
    schema = [{"name": f.name, "type": str(f.type)} for f in reader.schema]
    rows = sum(reader.get_batch(i).num_rows for i in range(reader.num_record_batches))
    return schema, rows


def summarize_annotations(path: Path) -> tuple[dict, pd.DataFrame, str]:
    df = pd.read_feather(path)
    body_col = first_column(df.columns, ["bodyid", "body_id", "body", "segment_id", "segment"])
    if body_col is None:
        raise ValueError(f"Could not identify body ID column in annotations: {list(df.columns)}")
    out = {
        "rows": int(len(df)),
        "body_id_column": body_col,
        "unique_body_ids": int(df[body_col].nunique(dropna=True)),
        "columns": [str(c) for c in df.columns],
    }
    detected: dict[str, str] = {}
    aliases = {
        "type": ["type"],
        "instance": ["instance"],
        "superclass": ["superclass"],
        "class": ["class", "cell_class"],
        "soma_side": ["somaSide", "soma_side"],
        "soma_neuromere": ["somaNeuromere", "soma_neuromere"],
        "status": ["status"],
        "status_label": ["statusLabel", "status_label"],
        "root_side": ["rootSide", "root_side"],
        "dimorphism": ["dimorphism"],
    }
    for name, candidates in aliases.items():
        col = first_column(df.columns, candidates)
        if col is not None:
            detected[name] = col
            if name in {"status", "status_label", "superclass", "class", "soma_neuromere", "dimorphism"}:
                out.setdefault("value_counts", {})[name] = compact_counts(df[col])
    out["detected_annotation_columns"] = detected
    return out, df, body_col


def summarize_neurotransmitters(path: Path) -> tuple[dict, pd.DataFrame, str, str]:
    df = pd.read_feather(path)
    body_col = first_column(df.columns, ["bodyid", "body_id", "body", "segment_id", "segment"])
    nt_col = first_column(df.columns, [
        "consensus_nt", "predicted_nt", "celltype_predicted_nt", "neurotransmitter", "nt"
    ])
    if body_col is None or nt_col is None:
        raise ValueError(
            "Could not identify body/neurotransmitter columns: " + str(list(df.columns))
        )
    return {
        "rows": int(len(df)),
        "body_id_column": body_col,
        "neurotransmitter_column": nt_col,
        "unique_body_ids": int(df[body_col].nunique(dropna=True)),
        "top_neurotransmitters": compact_counts(df[nt_col], 20),
        "columns": [str(c) for c in df.columns],
    }, df, body_col, nt_col


def _join_nt(
    annotations: pd.DataFrame,
    annotation_body_col: str,
    nts: pd.DataFrame,
    nt_body_col: str,
    nt_col: str,
) -> pd.DataFrame:
    left = annotations.copy()
    nt_cols = [nt_body_col, nt_col]
    for candidate in [
        "predicted_nt", "predicted_nt_confidence",
        "celltype_predicted_nt", "celltype_predicted_nt_confidence",
        "consensus_nt",
    ]:
        actual = first_column(nts.columns, [candidate])
        if actual is not None and actual not in nt_cols:
            nt_cols.append(actual)
    right = nts[nt_cols].drop_duplicates(subset=[nt_body_col])
    return left.merge(right, left_on=annotation_body_col, right_on=nt_body_col, how="left", validate="one_to_one")


def _known_mask(series: pd.Series) -> pd.Series:
    return ~series.astype("string").fillna("<NA>").str.lower().isin(UNKNOWN_NT)


def _nt_summary(joined: pd.DataFrame, nt_col: str) -> dict:
    known = _known_mask(joined[nt_col])
    return {
        "bodies": int(len(joined)),
        "with_nt_row": int(joined[nt_col].notna().sum()),
        "with_known_consensus_nt": int(known.sum()),
        "known_consensus_fraction": float(known.mean()),
        "consensus_counts": compact_counts(joined[nt_col], 20),
    }


def _nt_resolution_summary(joined: pd.DataFrame, consensus_col: str) -> dict:
    consensus = joined[consensus_col].astype("string")
    resolved = consensus.copy()
    source = pd.Series("consensus", index=joined.index, dtype="string")
    unresolved = ~_known_mask(consensus)

    pred_col = first_column(joined.columns, ["predicted_nt"])
    pred_conf_col = first_column(joined.columns, ["predicted_nt_confidence"])
    if pred_col is not None and pred_conf_col is not None:
        pred_known = _known_mask(joined[pred_col])
        pred_conf = pd.to_numeric(joined[pred_conf_col], errors="coerce")
        use_pred = unresolved & pred_known & (pred_conf >= 0.5)
        resolved.loc[use_pred] = joined.loc[use_pred, pred_col].astype("string")
        source.loc[use_pred] = "predicted_nt_conf>=0.5"
        unresolved = ~_known_mask(resolved)

    cell_col = first_column(joined.columns, ["celltype_predicted_nt"])
    cell_conf_col = first_column(joined.columns, ["celltype_predicted_nt_confidence"])
    if cell_col is not None and cell_conf_col is not None:
        cell_known = _known_mask(joined[cell_col])
        cell_conf = pd.to_numeric(joined[cell_conf_col], errors="coerce")
        use_cell = unresolved & cell_known & (cell_conf >= 0.5)
        resolved.loc[use_cell] = joined.loc[use_cell, cell_col].astype("string")
        source.loc[use_cell] = "celltype_predicted_nt_conf>=0.5"
        unresolved = ~_known_mask(resolved)

    return {
        "policy": (
            "consensus_nt; if unresolved, predicted_nt with confidence>=0.5; "
            "then celltype_predicted_nt with confidence>=0.5; never invent a transmitter"
        ),
        "resolved_bodies": int((~unresolved).sum()),
        "resolved_fraction": float((~unresolved).mean()),
        "unresolved_bodies": int(unresolved.sum()),
        "resolved_counts": compact_counts(resolved, 20),
        "resolution_source_counts": compact_counts(source.where(~unresolved, "unresolved"), 10),
    }


def summarize_join(
    annotations: pd.DataFrame,
    annotation_body_col: str,
    nts: pd.DataFrame,
    nt_body_col: str,
    nt_col: str,
) -> dict:
    joined = _join_nt(annotations, annotation_body_col, nts, nt_body_col, nt_col)
    return {
        **_nt_summary(joined, nt_col),
        "resolution_without_guessing": _nt_resolution_summary(joined, nt_col),
    }


def summarize_official_candidate_set(
    annotations: pd.DataFrame,
    annotation_body_col: str,
    nts: pd.DataFrame,
    nt_body_col: str,
    nt_col: str,
) -> dict:
    superclass_col = first_column(annotations.columns, ["superclass"])
    if superclass_col is None:
        raise ValueError("MaleCNS annotation table has no superclass column")
    superclass = annotations[superclass_col].astype("string")
    # This mirrors the criterion in the paper repository's quantification
    # notebook: superclass exists and its name does not contain 'tbc'.
    mask = superclass.notna() & ~superclass.str.contains("tbc", case=False, na=False)
    candidates = annotations.loc[mask].copy()
    joined = _join_nt(candidates, annotation_body_col, nts, nt_body_col, nt_col)
    return {
        "selection_rule": "superclass is non-null and does not contain 'tbc'",
        "reference_code": OFFICIAL_QUANTIFICATION_CODE,
        "candidate_bodies": int(candidates[annotation_body_col].nunique()),
        "superclass_counts": compact_counts(candidates[superclass_col], 40),
        "nt_coverage": {
            **_nt_summary(joined, nt_col),
            "resolution_without_guessing": _nt_resolution_summary(joined, nt_col),
        },
        "paper_reported_neurons": 166691,
        "note": (
            "The paper-level count and this flat-table selection need not be identical; "
            "do not force equality without a release-specific definition."
        ),
    }


def summarize_connectivity(path: Path) -> dict:
    schema, rows = arrow_schema(path)
    columns = [x["name"] for x in schema]
    pre = first_column(columns, ["body_pre", "bodypre", "pre", "source", "source_id"])
    post = first_column(columns, ["body_post", "bodypost", "post", "target", "target_id"])
    weight = first_column(columns, ["weight", "syn_count", "synapse_count", "count"])
    if pre is None or post is None or weight is None:
        raise ValueError(
            f"Could not identify pre/post/weight columns in connectivity schema: {columns}"
        )
    return {
        "rows": int(rows),
        "pre_column": pre,
        "post_column": post,
        "weight_column": weight,
        "schema": schema,
    }


def file_record(path: Path, url: str) -> dict:
    return {
        "path": str(path),
        "url": url,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--neurotransmitters", type=Path, required=True)
    p.add_argument("--connectivity", type=Path, required=True)
    p.add_argument("--annotations-url", required=True)
    p.add_argument("--neurotransmitters-url", required=True)
    p.add_argument("--connectivity-url", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    for path in [args.annotations, args.neurotransmitters, args.connectivity]:
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(path)

    ann_summary, ann_df, ann_body = summarize_annotations(args.annotations)
    nt_summary, nt_df, nt_body, nt_col = summarize_neurotransmitters(args.neurotransmitters)
    manifest = {
        "schema_version": 4,
        "dataset": DATASET,
        "canonical_anatomy": True,
        "official_project": "FlyEM/Janelia + Cambridge + MRC LMB + Google Research",
        "license": "CC-BY",
        "files": {
            "annotations": file_record(args.annotations, args.annotations_url),
            "neurotransmitters": file_record(args.neurotransmitters, args.neurotransmitters_url),
            "connectivity": file_record(args.connectivity, args.connectivity_url),
        },
        "annotations": ann_summary,
        "neurotransmitters": nt_summary,
        "annotation_nt_join": summarize_join(ann_df, ann_body, nt_df, nt_body, nt_col),
        "official_notebook_style_candidate_set": summarize_official_candidate_set(
            ann_df, ann_body, nt_df, nt_body, nt_col
        ),
        "connectivity": summarize_connectivity(args.connectivity),
        "interpretation": {
            "is_executable_dynamics_model": False,
            "note": "MaleCNS is structural connectome data. Neural dynamics are a separately versioned model layer.",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
