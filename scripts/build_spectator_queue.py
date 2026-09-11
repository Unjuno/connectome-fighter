#!/usr/bin/env python3
"""Build a 3-clip spectator queue from a canonical MaleCNS render run.

This is a presentation/export step only. Dynamic spike events are joined to
released MaleCNS structural annotations after the policy has acted. Nothing
produced here is fed back into the controller or learning path.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

ACTION_NAMES = {
    0: "NEUTRAL",
    1: "FORWARD",
    2: "BACKWARD",
    3: "UP",
    4: "DOWN",
    5: "A",
    6: "B",
    7: "C",
}


def read_json(path: Path | None, default):
    if path is None:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def clean(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"<na>", "nan", "none"} else None


def top_categories(table: pd.DataFrame, column: str, top_n: int) -> list[dict]:
    if column not in table.columns or table.empty:
        return []
    c: Counter[str] = Counter()
    for value, n in zip(table[column], table["spikes"]):
        key = clean(value)
        if key:
            c[key] += int(n)
    total = sum(c.values())
    return [
        {
            "name": name,
            "spikes": int(spikes),
            "fraction": (float(spikes) / total) if total else 0.0,
        }
        for name, spikes in c.most_common(top_n)
    ]


def activity_summary(
    spikes_path: Path,
    decisions_path: Path,
    structure_path: Path,
    *,
    top_n: int = 10,
    timeline_top_n: int = 6,
) -> dict:
    spikes = pd.read_parquet(spikes_path, columns=["decision_index", "body_id"])
    structure = pd.read_csv(structure_path, compression="gzip")
    decisions = read_jsonl(decisions_path)

    if spikes.empty:
        timeline = []
        for row in decisions:
            action_id = int(row.get("action", 0))
            timeline.append(
                {
                    "decision_index": int(row.get("decision_index", len(timeline))),
                    "frame": int(row.get("frame", 0)),
                    "action": ACTION_NAMES.get(action_id, str(action_id)),
                    "total_spikes": 0,
                    "unique_bodies": 0,
                    "regions": [],
                    "superclasses": [],
                }
            )
        return {
            "total_spikes": 0,
            "unique_bodies": 0,
            "top_neuromeres": [],
            "top_superclasses": [],
            "top_types": [],
            "top_bodies": [],
            "timeline": timeline,
            "interpretation": "MaleCNS somaNeuromere/category summary; not physical neuron coordinates.",
        }

    body_counts = (
        spikes["body_id"]
        .value_counts()
        .rename_axis("bodyId")
        .reset_index(name="spikes")
    )
    merged = body_counts.merge(structure, on="bodyId", how="left", validate="one_to_one")

    top_bodies = []
    for row in merged.sort_values("spikes", ascending=False).head(top_n).itertuples(index=False):
        record = {"body_id": int(row.bodyId), "spikes": int(row.spikes)}
        for column in ["somaNeuromere", "superclass", "class", "type", "rootSide"]:
            if hasattr(row, column):
                value = clean(getattr(row, column))
                if value:
                    record[column] = value
        top_bodies.append(record)

    per_body = (
        spikes.groupby(["decision_index", "body_id"], sort=True)
        .size()
        .rename("spikes")
        .reset_index()
        .rename(columns={"body_id": "bodyId"})
        .merge(structure, on="bodyId", how="left", validate="many_to_one")
    )
    decision_by_index = {
        int(row.get("decision_index", i)): row for i, row in enumerate(decisions)
    }
    indices = sorted(
        set(int(x) for x in per_body["decision_index"].unique()).union(decision_by_index)
    )
    timeline = []
    for index in indices:
        chunk = per_body[per_body["decision_index"] == index]
        decision = decision_by_index.get(index, {})
        action_id = int(decision.get("action", 0))
        timeline.append(
            {
                "decision_index": int(index),
                "frame": int(decision.get("frame", 0)),
                "action": ACTION_NAMES.get(action_id, str(action_id)),
                "total_spikes": int(chunk["spikes"].sum()) if not chunk.empty else 0,
                "unique_bodies": int(chunk["bodyId"].nunique()) if not chunk.empty else 0,
                "regions": top_categories(chunk, "somaNeuromere", timeline_top_n),
                "superclasses": top_categories(chunk, "superclass", 4),
            }
        )

    return {
        "total_spikes": int(len(spikes)),
        "unique_bodies": int(body_counts.shape[0]),
        "top_neuromeres": top_categories(merged, "somaNeuromere", top_n),
        "top_superclasses": top_categories(merged, "superclass", top_n),
        "top_types": top_categories(merged, "type", top_n),
        "top_bodies": top_bodies,
        "timeline": timeline,
        "interpretation": (
            "Region activity is a post-hoc count of real MaleCNS body-ID spikes grouped by "
            "categorical somaNeuromere annotations; it is not a spatial coordinate reconstruction."
        ),
    }


def round_summary(status: dict) -> dict:
    audit = status.get("audit") or {}
    rounds = audit.get("rounds") or []
    out = []
    for row in rounds:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "round": row.get("round"),
                "remaining_hps": row.get("remaining_hps"),
                "rewards": row.get("rewards"),
            }
        )
    return {"rounds": out, "count": len(out)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--structure-index", type=Path, required=True)
    p.add_argument("--video-meta", type=Path, required=True)
    p.add_argument("--previous-queue", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--public-base", required=True, help="Stable release asset base ending in /spectator-latest/")
    p.add_argument("--source-run-url", required=True)
    p.add_argument("--next-expected-at", required=True)
    args = p.parse_args()

    status = read_json(args.run_dir / "status.json", {})
    video = read_json(args.video_meta, {})
    chars = status.get("characters") or [
        video.get("p1", {}).get("character"),
        video.get("p2", {}).get("character"),
    ]
    seeds = status.get("seeds") or [
        video.get("p1", {}).get("seed"),
        video.get("p2", {}).get("seed"),
    ]
    if len(chars) != 2 or len(seeds) != 2:
        raise ValueError("render status does not identify two fighters")

    base = args.public_base.rstrip("/") + "/"
    clip_id = f"{status.get('run_id', 'clip')}-{video.get('source_actions_run', 'run')}"
    p1_activity = activity_summary(
        args.run_dir / "p1-brain" / "spikes.parquet",
        args.run_dir / "p1-brain" / "decisions.jsonl",
        args.structure_index,
    )
    p2_activity = activity_summary(
        args.run_dir / "p2-brain" / "spikes.parquet",
        args.run_dir / "p2-brain" / "decisions.jsonl",
        args.structure_index,
    )
    duration = float(video.get("duration_seconds", 0.0))
    timeline_steps = max(len(p1_activity["timeline"]), len(p2_activity["timeline"]), 1)

    entry = {
        "clip_id": clip_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_url": urljoin(base, "latest-fight.mp4"),
        "duration_seconds": duration,
        "frames": int(video.get("frames", 0)),
        "round_count": int(video.get("rounds", video.get("round_count", 6))),
        "p1": {"character": str(chars[0]), "seed": int(seeds[0])},
        "p2": {"character": str(chars[1]), "seed": int(seeds[1])},
        "outcomes": round_summary(status),
        "activity": {
            "basis": "real MaleCNS body IDs grouped by somaNeuromere annotation",
            "timeline_step_seconds": (duration / timeline_steps) if duration > 0 else 1.0,
            "p1": p1_activity,
            "p2": p2_activity,
        },
        "source_run_url": args.source_run_url,
        "policy_pixel_access": False,
    }

    previous = read_json(args.previous_queue, {})
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
        clips.append(dict(old))
        seen.add(old_id)
        if len(clips) >= 3:
            break

    stable_names = ["latest-fight.mp4", "previous-1.mp4", "previous-2.mp4"]
    for index, clip in enumerate(clips):
        clip["video_url"] = urljoin(base, stable_names[index])
        clip["queue_slot"] = index

    queue = {
        "schema_version": 3,
        "mode": "rolling-pseudo-live",
        "learning_enabled": False,
        "poll_interval_seconds": 30,
        "next_expected_at": args.next_expected_at,
        "clips": clips,
        "current_clip_id": clip_id,
        "source_run_url": args.source_run_url,
        "note": (
            "Each clip is a fresh canonical MaleCNS + pinned Shiu LIF simulation. "
            "Brain activity is post-hoc structural annotation and never enters policy input."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "clips": len(clips),
                "current": clip_id,
                "next_expected_at": args.next_expected_at,
                "p1_timeline_steps": len(p1_activity["timeline"]),
                "p2_timeline_steps": len(p2_activity["timeline"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
