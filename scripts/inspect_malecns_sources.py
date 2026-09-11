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


def arrow_schema(path: Path) -> tuple[list[dict[str, str]], int]:
    source = pa.memory_map(str(path), "r")
    reader = ipc.open_file(source)
    schema = [{"name": f.name, "type": str(f.type)} for f in reader.schema]
    rows = 0
    for i in range(reader.num_record_batches):
        rows += reader.get_batch(i).num_rows
    return schema, rows


def summarize_annotations(path: Path) -> dict:
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
    for name in ["type", "instance", "superclass", "class", "cell_class", "soma_side", "soma_neuromere", "status"]:
        col = first_column(df.columns, [name])
        if col is not None:
            out.setdefault("detected_annotation_columns", {})[name] = col
    return out


def summarize_neurotransmitters(path: Path) -> dict:
    df = pd.read_feather(path)
    body_col = first_column(df.columns, ["bodyid", "body_id", "body", "segment_id", "segment"])
    nt_col = first_column(df.columns, [
        "predicted_nt", "consensus_nt", "celltype_predicted_nt", "neurotransmitter", "nt"
    ])
    if body_col is None or nt_col is None:
        raise ValueError(
            "Could not identify body/neurotransmitter columns: " + str(list(df.columns))
        )
    counts = (
        df[nt_col].astype("string").fillna("<NA>").value_counts(dropna=False).head(20).to_dict()
    )
    return {
        "rows": int(len(df)),
        "body_id_column": body_col,
        "neurotransmitter_column": nt_col,
        "unique_body_ids": int(df[body_col].nunique(dropna=True)),
        "top_neurotransmitters": {str(k): int(v) for k, v in counts.items()},
        "columns": [str(c) for c in df.columns],
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

    manifest = {
        "schema_version": 1,
        "dataset": DATASET,
        "canonical_anatomy": True,
        "official_project": "FlyEM/Janelia + Cambridge + MRC LMB + Google Research",
        "license": "CC-BY",
        "files": {
            "annotations": file_record(args.annotations, args.annotations_url),
            "neurotransmitters": file_record(args.neurotransmitters, args.neurotransmitters_url),
            "connectivity": file_record(args.connectivity, args.connectivity_url),
        },
        "annotations": summarize_annotations(args.annotations),
        "neurotransmitters": summarize_neurotransmitters(args.neurotransmitters),
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
