#!/usr/bin/env python3
"""Build a compact spectator-only morphology map for active MaleCNS bodies.

Only body IDs already present in the public replay are considered. Centerline
skeletons are downloaded from the official MaleCNS v1.0 public Google Storage
bucket and projected in the documented z-x view. The result is visualization
metadata only and is never read by the controller.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import urllib.error
import urllib.request

BASE = "https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc"


def active_scores(replay: dict) -> dict[int, int]:
    scores: dict[int, int] = {}
    for frame in replay.get("frames", []):
        for side in ("p1", "p2"):
            brain = ((frame.get(side) or {}).get("brain") or {})
            for row in brain.get("top_bodies", []):
                bid = int(row["body_id"])
                scores[bid] = scores.get(bid, 0) + int(row.get("spikes", 0))
    return scores


def parse_swc(text: str) -> list[tuple[float, float, float, float]]:
    nodes: dict[int, tuple[float, float, int]] = {}
    edges: list[tuple[float, float, float, float]] = []
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        try:
            node_id = int(float(parts[0]))
            x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
            parent = int(float(parts[6]))
        except ValueError:
            continue
        if not all(math.isfinite(v) for v in (x, y, z)):
            continue
        # Official MaleCNS download page demonstrates z-x projection with navis.
        nodes[node_id] = (z, x, parent)
        rows.append(node_id)
    for node_id in rows:
        z, x, parent = nodes[node_id]
        if parent < 0 or parent not in nodes:
            continue
        pz, px, _ = nodes[parent]
        edges.append((pz, px, z, x))
    return edges


def sample_edges(edges: list[tuple[float, float, float, float]], limit: int):
    if len(edges) <= limit:
        return edges
    step = len(edges) / limit
    return [edges[min(len(edges) - 1, int(i * step))] for i in range(limit)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replay", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-bodies", type=int, default=60)
    p.add_argument("--max-segments-per-body", type=int, default=240)
    p.add_argument("--timeout", type=float, default=20.0)
    args = p.parse_args()
    if args.max_bodies <= 0 or args.max_segments_per_body <= 0:
        p.error("limits must be positive")

    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    scores = active_scores(replay)
    selected = sorted(scores, key=lambda b: (-scores[b], b))[: args.max_bodies]

    neurons = {}
    missing = []
    all_u: list[float] = []
    all_v: list[float] = []
    for bid in selected:
        url = f"{BASE}/{bid}.swc"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "connectome-fighter-spectator/1"})
            with urllib.request.urlopen(req, timeout=args.timeout) as response:
                text = response.read().decode("utf-8", "replace")
            edges = sample_edges(parse_swc(text), args.max_segments_per_body)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            missing.append({"body_id": bid, "error": str(exc)[:160]})
            continue
        if not edges:
            missing.append({"body_id": bid, "error": "empty-or-unparseable-skeleton"})
            continue
        flat = [[round(a, 3), round(b, 3), round(c, 3), round(d, 3)] for a, b, c, d in edges]
        neurons[str(bid)] = {"score": scores[bid], "segments": flat}
        for a, b, c, d in edges:
            all_u.extend((a, c))
            all_v.extend((b, d))

    if not neurons:
        raise RuntimeError("No official MaleCNS skeleton could be loaded for active replay bodies")

    payload = {
        "schema_version": 1,
        "dataset": "male-cns:v1.0",
        "source": BASE + "/{bodyId}.swc",
        "source_kind": "official MaleCNS v1.0 centerline skeletons",
        "policy_access": False,
        "projection": "z-x",
        "source_coordinate_units": "8nm units",
        "selected_body_count": len(selected),
        "loaded_body_count": len(neurons),
        "missing": missing,
        "bounds": {
            "u_min": min(all_u), "u_max": max(all_u),
            "v_min": min(all_v), "v_max": max(all_v),
        },
        "neurons": neurons,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "selected": len(selected),
        "loaded": len(neurons),
        "missing": len(missing),
        "bytes": args.out.stat().st_size,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
