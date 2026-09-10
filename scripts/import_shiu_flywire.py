"""Normalize the Shiu et al. FlyWire connectivity tables into this repo's graph contract.

This script DOES NOT download or vendor FlyWire data. Supply the upstream
Completeness_*.csv and Connectivity_*.parquet files yourself, then retain the
produced manifest alongside the normalized files.

Semantics follow philshiu/Drosophila_brain_model/model.py: neuron order is the
completeness dataframe index; edges use Presynaptic_Index, Postsynaptic_Index,
and signed `Excitatory x Connectivity`. Parallel identical pre->post rows are
collapsed by signed summation, which is equivalent for the Shiu model's common
presynaptic event, additive synaptic update, and common delay. Any exact signed
cancellations are removed and counted in the manifest.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _require_columns(columns: Iterable[str], required: set[str], label: str) -> None:
    actual = set(map(str, columns))
    missing = sorted(required - actual)
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}; got {sorted(actual)}")


def _safe_node_ids(index) -> list[str]:
    # Read as object and stringify exactly once. Float-looking IDs are rejected
    # because FlyWire root IDs must not pass through IEEE-754 and lose precision.
    result: list[str] = []
    for raw in index.tolist():
        text = str(raw).strip()
        if not text or text.lower() in {"nan", "none"}:
            raise ValueError("Completeness index contains an empty node ID")
        if any(c in text.lower() for c in (".", "e+", "e-")):
            raise ValueError(
                f"Node ID {text!r} looks float-coerced; re-read source without floating-point conversion"
            )
        result.append(text)
    if len(set(result)) != len(result):
        raise ValueError("Completeness index contains duplicate node IDs")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completeness", type=Path, required=True)
    parser.add_argument("--connectivity", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-version", default="FlyWire 783 / Shiu public table")
    parser.add_argument(
        "--source-url",
        default="https://github.com/philshiu/Drosophila_brain_model",
        help="Canonical/traceable upstream location recorded in manifest",
    )
    parser.add_argument(
        "--license",
        default="CC BY-NC 4.0 (FlyWire public release data; verify current source terms before use)",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("Install the data extra: python -m pip install '.[data]'") from exc

    for path in (args.completeness, args.connectivity):
        if not path.is_file():
            raise FileNotFoundError(path)
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = [args.out / "nodes.csv", args.out / "edges.csv", args.out / "manifest.json"]
    if not args.force and any(p.exists() for p in outputs):
        raise FileExistsError("Output exists; use --force only after verifying the target directory")

    source_hashes = {
        args.completeness.name: sha256_file(args.completeness),
        args.connectivity.name: sha256_file(args.connectivity),
    }

    # dtype=object prevents pandas from intentionally treating the index column
    # as float. We still validate the final textual IDs below.
    comp = pd.read_csv(args.completeness, index_col=0, dtype=object)
    node_ids = _safe_node_ids(comp.index)

    required = {"Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"}
    con = pd.read_parquet(args.connectivity, columns=sorted(required))
    _require_columns(con.columns, required, "connectivity parquet")

    pre = pd.to_numeric(con["Presynaptic_Index"], errors="raise")
    post = pd.to_numeric(con["Postsynaptic_Index"], errors="raise")
    signed = pd.to_numeric(con["Excitatory x Connectivity"], errors="raise")

    # Integer endpoint checks must happen before cast, otherwise 1.5 -> 1 would
    # silently corrupt topology.
    if not ((pre % 1 == 0).all() and (post % 1 == 0).all()):
        raise ValueError("Connectivity endpoint indices must be integers")
    if not signed.notna().all():
        raise ValueError("Signed connectivity contains missing values")
    pre = pre.astype("int64")
    post = post.astype("int64")
    n_nodes = len(node_ids)
    if len(pre) == 0:
        raise ValueError("Connectivity table is empty")
    if pre.min() < 0 or post.min() < 0 or pre.max() >= n_nodes or post.max() >= n_nodes:
        raise ValueError("Connectivity index is outside completeness-table neuron range")

    table = pd.DataFrame({"pre": pre, "post": post, "signed": signed})
    zero_input_rows = int((table["signed"] == 0).sum())
    original_rows = int(len(table))

    # In Shiu's model every row has the same delay and is activated by the same
    # presynaptic spike; g += w is additive. Therefore summing signed weights for
    # identical (pre, post) pairs preserves that model's instantaneous update.
    grouped = table.groupby(["pre", "post"], sort=True, as_index=False)["signed"].sum()
    duplicate_rows_collapsed = original_rows - int(len(grouped))
    zero_after_aggregation = int((grouped["signed"] == 0).sum())
    grouped = grouped[grouped["signed"] != 0].copy()
    if grouped.empty:
        raise ValueError("No nonzero connections remain after aggregation")

    # Write through temporary files and rename after all validation completes.
    nodes_tmp = args.out / "nodes.csv.tmp"
    edges_tmp = args.out / "edges.csv.tmp"
    with nodes_tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["node_id"])
        writer.writerows((node_id,) for node_id in node_ids)

    with edges_tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["pre_id", "post_id", "magnitude", "sign"])
        for row in grouped.itertuples(index=False):
            value = float(row.signed)
            writer.writerow([
                node_ids[int(row.pre)], node_ids[int(row.post)],
                format(abs(value), ".9g"), 1 if value > 0 else -1,
            ])

    nodes_tmp.replace(args.out / "nodes.csv")
    edges_tmp.replace(args.out / "edges.csv")
    processed_hashes = {
        "nodes.csv": sha256_file(args.out / "nodes.csv"),
        "edges.csv": sha256_file(args.out / "edges.csv"),
    }

    # graph.load_graph currently requires source_sha256 as one 64-hex identity.
    # Hash the ordered source-file digests to identify this exact source pair.
    source_pair_identity = hashlib.sha256(
        json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    manifest = {
        "kind": "biological",
        "scope": "whole_brain",
        "dataset": "FlyWire FAFB",
        "source_url": args.source_url,
        "source_version": args.source_version,
        "source_sha256": source_pair_identity,
        "source_files_sha256": source_hashes,
        "license": args.license,
        "preprocessing": (
            "Neuron order from completeness index; Presynaptic_Index/Postsynaptic_Index map into that order; "
            "signed edge value from `Excitatory x Connectivity`; identical directed pairs aggregated by signed sum; "
            "zero signed edges removed. No synthetic edges added."
        ),
        "model_lineage": {
            "repository": "https://github.com/philshiu/Drosophila_brain_model",
            "paper_doi": "10.1038/s41586-024-07763-9",
            "reference_semantics": "model.py create_model()",
        },
        "processed_files_sha256": processed_hashes,
        "counts": {
            "neurons": n_nodes,
            "source_connectivity_rows": original_rows,
            "zero_source_rows": zero_input_rows,
            "duplicate_rows_collapsed": duplicate_rows_collapsed,
            "zero_pairs_after_signed_aggregation": zero_after_aggregation,
            "normalized_edges": int(len(grouped)),
            "excitatory_edges": int((grouped["signed"] > 0).sum()),
            "inhibitory_edges": int((grouped["signed"] < 0).sum()),
        },
        "warning": (
            "The FlyWire public release is non-commercially licensed. Re-check canonical FlyWire terms and citations "
            "for the exact dataset/version before publication or redistribution. This manifest does not relicense data."
        ),
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Validate our own normalized format before declaring success.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from connectome_fighter.graph import load_graph
    graph = load_graph(args.out, require_biological=True)
    report = {
        "status": "normalized_and_validated",
        "graph_sha256": graph.fingerprint(),
        "neurons": graph.n_nodes,
        "edges": graph.n_edges,
        "manifest": str(args.out / "manifest.json"),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
