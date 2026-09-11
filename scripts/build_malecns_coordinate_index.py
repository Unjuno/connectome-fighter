#!/usr/bin/env python3
"""Build a spectator-only MaleCNS body-ID coordinate index.

The index is joined only after experiments for visualization. It is never read by
the game policy or the Shiu LIF worker, so anatomical coordinates cannot leak
into action selection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    ann = pd.read_feather(args.annotations)
    required = {"bodyId", "pos_x", "pos_y", "pos_z"}
    missing = required - set(ann.columns)
    if missing:
        raise ValueError(f"MaleCNS annotation lacks coordinate columns: {sorted(missing)}")
    meta = pd.read_parquet(args.metadata, columns=["bodyId"])
    if meta.empty or meta["bodyId"].duplicated().any():
        raise ValueError("invalid canonical metadata body IDs")

    coords = ann[["bodyId", "pos_x", "pos_y", "pos_z"]].copy()
    coords = coords.drop_duplicates(subset=["bodyId"], keep=False)
    coords = meta.merge(coords, on="bodyId", how="left", validate="one_to_one")
    for c in ["pos_x", "pos_y", "pos_z"]:
        coords[c] = pd.to_numeric(coords[c], errors="coerce")
    valid = coords[["pos_x", "pos_y", "pos_z"]].notna().all(axis=1)
    valid_coords = coords.loc[valid].sort_values("bodyId", kind="stable").reset_index(drop=True)
    if len(valid_coords) < int(0.9 * len(meta)):
        raise RuntimeError(
            f"coordinate coverage unexpectedly low: {len(valid_coords)}/{len(meta)}"
        )

    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "body_coordinates.csv.gz"
    valid_coords.to_csv(csv_path, index=False, compression="gzip")
    bounds = {
        axis: {
            "min": float(valid_coords[axis].min()),
            "max": float(valid_coords[axis].max()),
        }
        for axis in ["pos_x", "pos_y", "pos_z"]
    }
    manifest = {
        "schema_version": 1,
        "dataset": "male-cns:v1.0",
        "purpose": "spectator-only-coordinate-index",
        "policy_access": False,
        "coordinate_columns": ["pos_x", "pos_y", "pos_z"],
        "canonical_bodies": int(len(meta)),
        "bodies_with_coordinates": int(len(valid_coords)),
        "coverage": float(len(valid_coords) / len(meta)),
        "bounds": bounds,
        "source_annotations_sha256": sha256(args.annotations),
        "canonical_metadata_sha256": sha256(args.metadata),
        "coordinates_sha256": sha256(csv_path),
        "interpretation_boundary": (
            "Coordinates are released MaleCNS annotation coordinates used only for "
            "post-hoc visualization. They are not inputs to the controller."
        ),
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
