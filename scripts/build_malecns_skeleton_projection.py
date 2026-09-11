#!/usr/bin/env python3
"""Fetch released MaleCNS SWC skeletons for the most active bodies in a clip.

The MaleCNS project publishes centerline skeletons in EM coordinates (8 nm
units). This script is spectator-only: it selects bodies from recorded spike
logs after the match, downloads their public SWC files, and stores a compact
X-Z projection. Morphology never enters the controller or learning path.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import urllib.error
import urllib.request

import pandas as pd

BASE = (
    "https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/"
    "skeletons-malecns/skeletons-swc"
)


def top_bodies(path: Path, count: int) -> list[tuple[int, int]]:
    frame = pd.read_parquet(path, columns=["body_id"])
    counts = frame["body_id"].value_counts().head(count)
    return [(int(body), int(n)) for body, n in counts.items()]


def fetch_swc(body_id: int, timeout: float) -> str:
    url = f"{BASE}/{body_id}.swc"
    request = urllib.request.Request(url, headers={"User-Agent": "connectome-fighter-spectator/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_projection(text: str, max_segments: int) -> tuple[list[list[float]], dict[str, float]]:
    nodes: dict[int, tuple[float, float, float, int]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        node_id = int(float(parts[0]))
        x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
        parent = int(float(parts[6]))
        nodes[node_id] = (x, y, z, parent)

    segments: list[list[float]] = []
    xs: list[float] = []
    zs: list[float] = []
    for node_id, (x, _y, z, parent) in nodes.items():
        if parent < 0 or parent not in nodes:
            continue
        px, _py, pz, _ = nodes[parent]
        segments.append([x, z, px, pz])
        xs.extend([x, px]); zs.extend([z, pz])

    if not segments:
        raise ValueError("SWC has no connected segments")
    if len(segments) > max_segments:
        stride = max(1, math.ceil(len(segments) / max_segments))
        segments = segments[::stride][:max_segments]

    bounds = {
        "x_min": min(xs), "x_max": max(xs),
        "z_min": min(zs), "z_max": max(zs),
    }
    return segments, bounds


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--bodies-per-side", type=int, default=6)
    p.add_argument("--max-segments-per-body", type=int, default=180)
    p.add_argument("--timeout", type=float, default=30.0)
    args = p.parse_args()
    if args.bodies_per_side <= 0 or args.max_segments_per_body <= 0:
        p.error("body and segment limits must be positive")

    selected = {
        "p1": top_bodies(args.run_dir / "p1-brain" / "spikes.parquet", args.bodies_per_side),
        "p2": top_bodies(args.run_dir / "p2-brain" / "spikes.parquet", args.bodies_per_side),
    }
    unique = sorted({body for rows in selected.values() for body, _ in rows})
    morphology: dict[int, dict] = {}
    failures: dict[int, str] = {}
    global_x: list[float] = []
    global_z: list[float] = []

    for body_id in unique:
        try:
            swc = fetch_swc(body_id, args.timeout)
            segments, bounds = parse_projection(swc, args.max_segments_per_body)
            morphology[body_id] = {
                "body_id": body_id,
                "source": f"{BASE}/{body_id}.swc",
                "coordinate_space": "MaleCNS EM",
                "coordinate_units": "8 nm",
                "projection": "x-z",
                "segments": segments,
                "bounds": bounds,
            }
            global_x.extend([bounds["x_min"], bounds["x_max"]])
            global_z.extend([bounds["z_min"], bounds["z_max"]])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            failures[body_id] = f"{type(exc).__name__}: {exc}"

    if not morphology:
        raise RuntimeError(f"No released skeletons could be loaded: {failures}")

    sides: dict[str, list[dict]] = {}
    for side, rows in selected.items():
        sides[side] = [
            {
                "body_id": body,
                "clip_spikes": spikes,
                "morphology": morphology.get(body),
            }
            for body, spikes in rows
            if body in morphology
        ]

    payload = {
        "schema_version": 1,
        "dataset": "male-cns:v1.0",
        "purpose": "spectator-only-released-skeleton-projection",
        "policy_access": False,
        "projection": "x-z",
        "coordinate_space": "MaleCNS EM",
        "coordinate_units": "8 nm",
        "source_base": BASE,
        "bounds": {
            "x_min": min(global_x), "x_max": max(global_x),
            "z_min": min(global_z), "z_max": max(global_z),
        },
        "sides": sides,
        "failed_body_ids": {str(k): v for k, v in failures.items()},
        "interpretation_boundary": (
            "Released neuron centerline skeletons are selected only after the fight from recorded spike logs. "
            "They are visualization data and are never policy inputs."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "requested_bodies": len(unique),
        "loaded_bodies": len(morphology),
        "failed_bodies": len(failures),
        "p1": len(sides["p1"]),
        "p2": len(sides["p2"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
