#!/usr/bin/env python3
"""Build spectator-only MaleCNS morphology for one recorded fight clip.

The active layer is selected post-hoc from real recorded spike body IDs. A
separate versioned context atlas supplies a lightweight whole-CNS background
from official released MaleCNS SWC centerlines. Neither layer is available to
the controller or learning path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import urllib.error
import urllib.request

BASE = (
    "https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/"
    "skeletons-malecns/skeletons-swc"
)
DEFAULT_ATLAS_URL = (
    "https://github.com/Unjuno/connectome-fighter/releases/download/"
    "malecns-context-atlas-v1/malecns-context-atlas-xz.json"
)
DEFAULT_ATLAS_SHA256 = "f7c691d6c80820bf46c6bd09fd5d9dc92d0ec4f45fd9a0e4e1bd91132e729107"


def top_bodies(path: Path, count: int) -> list[tuple[int, int]]:
    import pandas as pd

    frame = pd.read_parquet(path, columns=["body_id"])
    counts = frame["body_id"].value_counts().head(count)
    return [(int(body), int(n)) for body, n in counts.items()]


def fetch_swc(body_id: int, timeout: float) -> str:
    url = f"{BASE}/{body_id}.swc"
    request = urllib.request.Request(url, headers={"User-Agent": "connectome-fighter-spectator/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def fetch_context_atlas(url: str, expected_sha256: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "connectome-fighter-spectator/2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    actual = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and actual != expected_sha256.lower():
        raise ValueError(f"context atlas SHA-256 mismatch: {actual}")
    atlas = json.loads(raw.decode("utf-8"))
    if atlas.get("schema_version") != 1:
        raise ValueError("unsupported context atlas schema")
    if atlas.get("kind") != "male-cns-context-atlas-xz":
        raise ValueError("invalid context atlas kind")
    if atlas.get("dataset") != "male-cns:v1.0":
        raise ValueError("context atlas dataset mismatch")
    if atlas.get("policy_access") is not False:
        raise ValueError("context atlas must be spectator-only")
    if atlas.get("atlas_kind") != "deterministic-stratified-released-skeleton-sample":
        raise ValueError("context atlas sampling contract mismatch")
    if atlas.get("projection") != "x-z" or atlas.get("coordinate_space") != "MaleCNS EM":
        raise ValueError("context atlas coordinate contract mismatch")
    if atlas.get("coordinate_units") != "8 nm":
        raise ValueError("context atlas coordinate units mismatch")
    segments = atlas.get("segments") or []
    bounds = atlas.get("bounds") or {}
    coverage = atlas.get("coverage") or {}
    if len(segments) < 1000 or int(coverage.get("loaded_bodies", 0)) < 48:
        raise ValueError("context atlas coverage is below spectator minimum")
    if not all(key in bounds for key in ("x_min", "x_max", "z_min", "z_max")):
        raise ValueError("context atlas bounds missing")
    boundary = str(atlas.get("interpretation_boundary") or "").lower()
    if "not an all-neuron rendering" not in boundary or "policy input" not in boundary:
        raise ValueError("context atlas interpretation boundary missing")
    atlas["sha256"] = actual
    return atlas


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
    p.add_argument("--atlas-url", default=DEFAULT_ATLAS_URL)
    p.add_argument("--atlas-sha256", default=DEFAULT_ATLAS_SHA256)
    p.add_argument("--atlas-timeout", type=float, default=30.0)
    args = p.parse_args()
    if args.bodies_per_side <= 0 or args.max_segments_per_body <= 0:
        p.error("body and segment limits must be positive")

    atlas = fetch_context_atlas(args.atlas_url, args.atlas_sha256, args.atlas_timeout)
    atlas_bounds = atlas["bounds"]
    global_x = [float(atlas_bounds["x_min"]), float(atlas_bounds["x_max"])]
    global_z = [float(atlas_bounds["z_min"]), float(atlas_bounds["z_max"])]

    selected = {
        "p1": top_bodies(args.run_dir / "p1-brain" / "spikes.parquet", args.bodies_per_side),
        "p2": top_bodies(args.run_dir / "p2-brain" / "spikes.parquet", args.bodies_per_side),
    }
    unique = sorted({body for rows in selected.values() for body, _ in rows})
    morphology: dict[int, dict] = {}
    failures: dict[int, str] = {}

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
        raise RuntimeError(f"No released active skeletons could be loaded: {failures}")

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

    coverage = atlas.get("coverage") or {}
    payload = {
        "schema_version": 2,
        "dataset": "male-cns:v1.0",
        "purpose": "spectator-only-context-atlas-plus-active-released-skeletons",
        "policy_access": False,
        "projection": "x-z",
        "coordinate_space": "MaleCNS EM",
        "coordinate_units": "8 nm",
        "source_base": BASE,
        "bounds": {
            "x_min": min(global_x), "x_max": max(global_x),
            "z_min": min(global_z), "z_max": max(global_z),
        },
        "atlas_segments": atlas["segments"],
        "atlas": {
            "source": args.atlas_url,
            "sha256": atlas["sha256"],
            "kind": atlas["kind"],
            "atlas_kind": atlas["atlas_kind"],
            "loaded_bodies": int(coverage.get("loaded_bodies", 0)),
            "segment_count": len(atlas["segments"]),
            "soma_neuromeres": coverage.get("soma_neuromeres") or [],
            "superclasses": coverage.get("superclasses") or [],
            "root_sides": coverage.get("root_sides") or [],
            "interpretation_boundary": atlas["interpretation_boundary"],
        },
        "sides": sides,
        "failed_body_ids": {str(k): v for k, v in failures.items()},
        "interpretation_boundary": (
            "The faint context layer is a deterministic stratified sample of official released MaleCNS SWC centerlines; it is not an all-neuron rendering. "
            "Bright clip-active centerlines are selected only after the fight from recorded spike body IDs. Both layers are spectator-only and never policy inputs."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "requested_active_bodies": len(unique),
        "loaded_active_bodies": len(morphology),
        "failed_active_bodies": len(failures),
        "p1": len(sides["p1"]),
        "p2": len(sides["p2"]),
        "atlas_bodies": int(coverage.get("loaded_bodies", 0)),
        "atlas_segments": len(atlas["segments"]),
        "atlas_sha256": atlas["sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
