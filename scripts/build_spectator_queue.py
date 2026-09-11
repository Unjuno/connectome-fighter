#!/usr/bin/env python3
"""Build a 3-clip spectator queue from a canonical MaleCNS render run.

The queue is a presentation artifact only. It summarizes recorded spike events
by released MaleCNS structural annotations and never feeds data back into the
policy or learning path. Decision-window activity samples are mapped across the
recorded video duration so the Vercel spectator can animate structural activity
while the fight video plays.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd


def read_json(path: Path | None, default):
    if path is None:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def clean(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"<na>", "nan", "none"} else None


def ranked_from_counter(counter: Counter, limit: int) -> list[dict]:
    return [{"name": str(k), "spikes": int(v)} for k, v in counter.most_common(limit)]


def counter_for_column(frame: pd.DataFrame, column: str) -> Counter:
    out: Counter = Counter()
    if column not in frame.columns:
        return out
    for value in frame[column]:
        key = clean(value)
        if key:
            out[key] += 1
    return out


def activity_bundle(
    spikes_path: Path,
    structure_path: Path,
    *,
    duration_seconds: float,
    top_n: int = 10,
    timeline_top_n: int = 6,
) -> dict:
    spikes = pd.read_parquet(spikes_path, columns=["decision_index", "body_id"])
    structure = pd.read_csv(structure_path, compression="gzip")
    if spikes.empty:
        return {
            "summary": {
                "total_spikes": 0,
                "unique_bodies": 0,
                "top_neuromeres": [],
                "top_superclasses": [],
                "top_types": [],
                "top_bodies": [],
                "interpretation": "Categorical MaleCNS structural annotations; not physical neuron coordinates.",
            },
            "timeline": [],
        }

    counts = spikes["body_id"].value_counts().rename_axis("bodyId").reset_index(name="spikes")
    merged_counts = counts.merge(structure, on="bodyId", how="left", validate="one_to_one")

    def grouped_counts(column: str) -> list[dict]:
        if column not in merged_counts.columns:
            return []
        c = Counter()
        for value, n in zip(merged_counts[column], merged_counts["spikes"]):
            key = clean(value)
            if key:
                c[key] += int(n)
        return ranked_from_counter(c, top_n)

    top_bodies = []
    for row in merged_counts.sort_values("spikes", ascending=False).head(top_n).itertuples(index=False):
        record = {"body_id": int(row.bodyId), "spikes": int(row.spikes)}
        for column in ["somaNeuromere", "superclass", "class", "type", "rootSide"]:
            if hasattr(row, column):
                value = clean(getattr(row, column))
                if value:
                    record[column] = value
        top_bodies.append(record)

    summary = {
        "total_spikes": int(len(spikes)),
        "unique_bodies": int(counts.shape[0]),
        "top_neuromeres": grouped_counts("somaNeuromere"),
        "top_superclasses": grouped_counts("superclass"),
        "top_types": grouped_counts("type"),
        "top_bodies": top_bodies,
        "interpretation": "Categorical MaleCNS structural annotations; not physical neuron coordinates.",
    }

    event_structure = spikes.merge(
        structure,
        left_on="body_id",
        right_on="bodyId",
        how="left",
        validate="many_to_one",
    )
    max_decision = int(spikes["decision_index"].max())
    decision_count = max_decision + 1
    if decision_count <= 0:
        decision_count = 1

    timeline = []
    for decision_index, window in event_structure.groupby("decision_index", sort=True):
        idx = int(decision_index)
        body_counts = window["body_id"].value_counts()
        top_body_rows = []
        for body_id, n in body_counts.head(5).items():
            annotation_rows = window.loc[window["body_id"] == body_id]
            annotation = annotation_rows.iloc[0] if not annotation_rows.empty else None
            record = {"body_id": int(body_id), "spikes": int(n)}
            if annotation is not None:
                for column in ["somaNeuromere", "superclass", "type"]:
                    if column in annotation.index:
                        value = clean(annotation[column])
                        if value:
                            record[column] = value
            top_body_rows.append(record)

        center_seconds = float(duration_seconds) * (idx + 0.5) / decision_count
        timeline.append({
            "decision_index": idx,
            "t_seconds": center_seconds,
            "total_spikes": int(len(window)),
            "unique_bodies": int(window["body_id"].nunique()),
            "neuromeres": ranked_from_counter(counter_for_column(window, "somaNeuromere"), timeline_top_n),
            "superclasses": ranked_from_counter(counter_for_column(window, "superclass"), timeline_top_n),
            "types": ranked_from_counter(counter_for_column(window, "type"), timeline_top_n),
            "top_bodies": top_body_rows,
        })

    return {"summary": summary, "timeline": timeline}


def round_summary(status: dict) -> dict:
    audit = status.get("audit") or {}
    rounds = audit.get("rounds") or []
    out = []
    for ordinal, row in enumerate(rounds, start=1):
        if not isinstance(row, dict):
            continue
        out.append({
            "round": row.get("round") or ordinal,
            "remaining_hps": row.get("remaining_hps"),
            "rewards": row.get("rewards"),
        })
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
    chars = status.get("characters") or [video.get("p1", {}).get("character"), video.get("p2", {}).get("character")]
    seeds = status.get("seeds") or [video.get("p1", {}).get("seed"), video.get("p2", {}).get("seed")]
    if len(chars) != 2 or len(seeds) != 2:
        raise ValueError("render status does not identify two fighters")

    duration_seconds = float(video.get("duration_seconds", 0.0))
    base = args.public_base.rstrip("/") + "/"
    clip_id = f"{status.get('run_id','clip')}-{video.get('source_actions_run','run')}"
    p1_activity = activity_bundle(
        args.run_dir / "p1-brain" / "spikes.parquet",
        args.structure_index,
        duration_seconds=duration_seconds,
    )
    p2_activity = activity_bundle(
        args.run_dir / "p2-brain" / "spikes.parquet",
        args.structure_index,
        duration_seconds=duration_seconds,
    )
    entry = {
        "clip_id": clip_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_url": urljoin(base, "latest-fight.mp4"),
        "duration_seconds": duration_seconds,
        "frames": int(video.get("frames", 0)),
        "round_count": int(video.get("rounds", video.get("round_count", 6))),
        "p1": {"character": str(chars[0]), "seed": int(seeds[0])},
        "p2": {"character": str(chars[1]), "seed": int(seeds[1])},
        "outcomes": round_summary(status),
        "activity": {
            "p1": p1_activity["summary"],
            "p2": p2_activity["summary"],
        },
        "activity_timeline": {
            "p1": p1_activity["timeline"],
            "p2": p2_activity["timeline"],
            "mapping": "Decision windows are linearly mapped over the spectator clip duration; decision_interval=60 FightingICE frames (~1 game second).",
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
        "note": "Each clip is a fresh canonical MaleCNS + pinned Shiu LIF simulation. Brain activity is post-hoc structural annotation and never enters policy input.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "clips": len(clips),
        "current": clip_id,
        "p1_activity_samples": len(p1_activity["timeline"]),
        "p2_activity_samples": len(p2_activity["timeline"]),
        "next_expected_at": args.next_expected_at,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
