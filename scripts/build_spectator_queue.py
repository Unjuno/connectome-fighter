#!/usr/bin/env python3
"""Build a 3-clip spectator queue from a canonical MaleCNS render run.

The queue is a presentation artifact only. It summarizes recorded spike events
by released MaleCNS structural annotations and never feeds data back into the
policy or learning path.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def clean(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"<na>", "nan", "none"} else None


def activity_summary(spikes_path: Path, structure_path: Path, top_n: int = 10) -> dict:
    spikes = pd.read_parquet(spikes_path, columns=["body_id"])
    structure = pd.read_csv(structure_path, compression="gzip")
    if spikes.empty:
        return {"total_spikes": 0, "unique_bodies": 0, "top_neuromeres": [], "top_superclasses": [], "top_types": [], "top_bodies": []}

    counts = spikes["body_id"].value_counts().rename_axis("bodyId").reset_index(name="spikes")
    merged = counts.merge(structure, on="bodyId", how="left", validate="one_to_one")

    def grouped(column: str) -> list[dict]:
        if column not in merged.columns:
            return []
        c = Counter()
        for value, n in zip(merged[column], merged["spikes"]):
            key = clean(value)
            if key:
                c[key] += int(n)
        return [{"name": k, "spikes": int(v)} for k, v in c.most_common(top_n)]

    top_bodies = []
    for row in merged.sort_values("spikes", ascending=False).head(top_n).itertuples(index=False):
        record = {"body_id": int(row.bodyId), "spikes": int(row.spikes)}
        for column in ["somaNeuromere", "superclass", "class", "type", "rootSide"]:
            if hasattr(row, column):
                value = clean(getattr(row, column))
                if value:
                    record[column] = value
        top_bodies.append(record)

    return {
        "total_spikes": int(len(spikes)),
        "unique_bodies": int(counts.shape[0]),
        "top_neuromeres": grouped("somaNeuromere"),
        "top_superclasses": grouped("superclass"),
        "top_types": grouped("type"),
        "top_bodies": top_bodies,
        "interpretation": "Categorical MaleCNS structural annotations; not physical neuron coordinates.",
    }


def round_summary(status: dict) -> dict:
    audit = status.get("audit") or {}
    rounds = audit.get("rounds") or []
    out = []
    for row in rounds:
        if not isinstance(row, dict):
            continue
        out.append({
            "round": row.get("round"),
            "remaining_hps": row.get("remaining_hps"),
            "rewards": row.get("rewards"),
        })
    return {"rounds": out, "count": len(out)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--structure-index", type=Path, required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--video-meta", type=Path, required=True)
    p.add_argument("--previous-queue", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--public-base", required=True)
    p.add_argument("--source-run-url", required=True)
    p.add_argument("--next-expected-at", required=True)
    args = p.parse_args()

    status = read_json(args.run_dir / "status.json", {})
    video = read_json(args.video_meta, {})
    chars = status.get("characters") or [video.get("p1", {}).get("character"), video.get("p2", {}).get("character")]
    seeds = status.get("seeds") or [video.get("p1", {}).get("seed"), video.get("p2", {}).get("seed")]
    if len(chars) != 2 or len(seeds) != 2:
        raise ValueError("render status does not identify two fighters")

    clip_id = f"{status.get('run_id','clip')}-{video.get('source_actions_run','run')}"
    filename = args.video.name
    public_url = urljoin(args.public_base.rstrip("/") + "/", f"fights/{filename}")
    entry = {
        "clip_id": clip_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_url": public_url,
        "duration_seconds": float(video.get("duration_seconds", 0.0)),
        "frames": int(video.get("frames", 0)),
        "round_count": int(video.get("round_count", status.get("games_requested", 0))),
        "p1": {"character": str(chars[0]), "seed": int(seeds[0])},
        "p2": {"character": str(chars[1]), "seed": int(seeds[1])},
        "outcomes": round_summary(status),
        "activity": {
            "p1": activity_summary(args.run_dir / "p1-brain" / "spikes.parquet", args.structure_index),
            "p2": activity_summary(args.run_dir / "p2-brain" / "spikes.parquet", args.structure_index),
        },
        "source_run_url": args.source_run_url,
        "policy_pixel_access": False,
    }

    previous = read_json(args.previous_queue, {}) if args.previous_queue else {}
    previous_entries = previous.get("clips") if isinstance(previous, dict) else []
    if not isinstance(previous_entries, list):
        previous_entries = []
    clips = [entry]
    seen = {clip_id}
    for old in previous_entries:
        if not isinstance(old, dict):
            continue
        old_id = str(old.get("clip_id", ""))
        if not old_id or old_id in seen:
            continue
        clips.append(old)
        seen.add(old_id)
        if len(clips) >= 3:
            break

    queue = {
        "schema_version": 1,
        "mode": "rolling-pseudo-live",
        "learning_enabled": False,
        "poll_interval_seconds": 30,
        "next_expected_at": args.next_expected_at,
        "clips": clips,
        "current_clip_id": clip_id,
        "source_run_url": args.source_run_url,
        "note": "Each clip is a fresh canonical MaleCNS + pinned Shiu LIF simulation. Queue activity is post-hoc structural annotation only.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "clips": len(clips), "current": clip_id, "next_expected_at": args.next_expected_at}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
