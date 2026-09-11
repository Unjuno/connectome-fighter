"""Build reproducible game<->FlyWire routing and aligned node coordinates.

The biological boundary is restricted to annotated FlyWire `sensory` neurons
for input and `descending` neurons for output. Assignment of the 18 game
features to sensory neurons is artificial and MUST NOT be described as a
biological sensory code.

To avoid treating negative game values as inhibitory current into sensory
neurons, each feature is split into positive/negative half-wave channels:
  polarity +1 -> max(x, 0)
  polarity -1 -> max(-x, 0)

When ``--metadata-out`` is supplied, the script also writes coordinate arrays
aligned exactly to ``nodes.csv``. Coordinates are copied from the pinned
FlyWire annotation table; no anatomical location is inferred for missing rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import random

import numpy as np

OBS_DIM = 18


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_node_ids(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids = [str(r["node_id"]).strip() for r in rows]
    if not ids or len(ids) != len(set(ids)) or any(not x for x in ids):
        raise ValueError("Invalid normalized node list")
    return ids


def _finite_float(value: str) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")
    return parsed if np.isfinite(parsed) else float("nan")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nodes", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--metadata-out", type=Path)
    p.add_argument("--seed", type=int, default=20260911)
    p.add_argument("--neurons-per-polarity-per-feature", type=int, default=32)
    p.add_argument("--input-scale", type=float, default=0.25)
    p.add_argument("--annotation-source", required=True)
    p.add_argument("--annotation-version", required=True)
    args = p.parse_args()
    if args.neurons_per_polarity_per_feature <= 0:
        p.error("neurons per polarity/feature must be positive")
    if not (0 < args.input_scale <= 10):
        p.error("input scale must be in (0, 10]")

    node_ids = load_node_ids(args.nodes)
    node_index = {root_id: i for i, root_id in enumerate(node_ids)}
    positions = np.full((len(node_ids), 3), np.nan, dtype=np.float32)
    has_position = np.zeros(len(node_ids), dtype=np.bool_)

    sensory: set[str] = set()
    descending: set[str] = set()
    with args.annotations.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"root_id", "super_class"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Annotation TSV must contain {sorted(required)}")
        has_xyz = {"pos_x", "pos_y", "pos_z"}.issubset(reader.fieldnames)
        for row in reader:
            root = str(row["root_id"]).strip()
            idx = node_index.get(root)
            if idx is None:
                continue
            superclass = str(row["super_class"]).strip().lower()
            if superclass == "sensory":
                sensory.add(root)
            elif superclass == "descending":
                descending.add(root)
            if has_xyz:
                xyz = [_finite_float(row.get(k, "")) for k in ("pos_x", "pos_y", "pos_z")]
                if all(np.isfinite(v) for v in xyz):
                    positions[idx] = np.asarray(xyz, dtype=np.float32)
                    has_position[idx] = True

    sensory_ids = sorted(sensory, key=lambda x: (len(x), x))
    output_ids = sorted(descending, key=lambda x: (len(x), x))
    needed = OBS_DIM * 2 * args.neurons_per_polarity_per_feature
    if len(sensory_ids) < needed:
        raise ValueError(f"Need {needed} sensory neurons, found {len(sensory_ids)}")
    if not output_ids:
        raise ValueError("No descending neurons overlap the normalized graph")

    rng = random.Random(args.seed)
    selected = sensory_ids.copy()
    rng.shuffle(selected)
    selected = selected[:needed]

    input_nodes: list[int] = []
    input_root_ids: list[str] = []
    input_features: list[int] = []
    input_polarities: list[int] = []
    cursor = 0
    for feature in range(OBS_DIM):
        for polarity in (1, -1):
            group = selected[cursor:cursor + args.neurons_per_polarity_per_feature]
            cursor += args.neurons_per_polarity_per_feature
            for root in group:
                input_nodes.append(node_index[root])
                input_root_ids.append(root)
                input_features.append(feature)
                input_polarities.append(polarity)

    output_nodes = [node_index[root] for root in output_ids]
    payload = {
        "schema_version": 1,
        "graph_nodes_sha256": sha256_file(args.nodes),
        "annotation_source": args.annotation_source,
        "annotation_version": args.annotation_version,
        "annotation_file_sha256": sha256_file(args.annotations),
        "selection": {
            "input_super_class": "sensory",
            "output_super_class": "descending",
            "sensory_candidates_in_graph": len(sensory_ids),
            "descending_candidates_in_graph": len(output_ids),
            "routing_seed": args.seed,
            "neurons_per_polarity_per_feature": args.neurons_per_polarity_per_feature,
            "encoding": "half_wave_positive_negative",
            "input_scale": args.input_scale,
            "note": "Feature-to-sensory assignment is artificial; only sensory/descending population boundaries are annotation-derived."
        },
        "input_nodes": input_nodes,
        "input_root_ids": input_root_ids,
        "input_features": input_features,
        "input_polarities": input_polarities,
        "output_nodes": output_nodes,
        "output_root_ids": output_ids,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload["routing_sha256"] = hashlib.sha256(encoded).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    metadata_summary = None
    if args.metadata_out is not None:
        args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
        if has_position.any():
            valid = positions[has_position]
            bounds_min = valid.min(axis=0).astype(np.float32)
            bounds_max = valid.max(axis=0).astype(np.float32)
        else:
            bounds_min = np.full(3, np.nan, dtype=np.float32)
            bounds_max = np.full(3, np.nan, dtype=np.float32)
        np.savez_compressed(
            args.metadata_out,
            positions=positions,
            has_position=has_position,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            coordinate_space=np.asarray(["FlyWire annotation voxel coordinates (4x4x40 nm voxels)"]),
            annotation_version=np.asarray([args.annotation_version]),
        )
        metadata_summary = {
            "file": str(args.metadata_out),
            "positioned_nodes": int(has_position.sum()),
            "sha256": sha256_file(args.metadata_out),
        }

    print(json.dumps({
        "status": "routing_created",
        "sensory_candidates": len(sensory_ids),
        "selected_input_neurons": len(input_nodes),
        "descending_outputs": len(output_nodes),
        "routing_sha256": payload["routing_sha256"],
        "artificial_mapping": True,
        "node_metadata": metadata_summary,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
