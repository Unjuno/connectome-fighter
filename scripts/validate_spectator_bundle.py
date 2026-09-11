#!/usr/bin/env python3
"""Validate the frozen rolling-spectator contract before publishing assets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--video-meta", type=Path, required=True)
    p.add_argument("--require-three-clips", action="store_true")
    args = p.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    video = json.loads(args.video_meta.read_text(encoding="utf-8"))

    assert int(queue.get("schema_version", 0)) >= 4, queue.get("schema_version")
    assert queue.get("mode") == "rolling-pseudo-live"
    assert queue.get("learning_enabled") is False
    assert int(queue.get("poll_interval_seconds", 0)) == 30
    assert queue.get("next_expected_at")

    clips = queue.get("clips") or []
    assert 1 <= len(clips) <= 3, len(clips)
    if args.require_three_clips:
        assert len(clips) == 3, len(clips)
    assert queue.get("current_clip_id") == clips[0].get("clip_id")

    expected_names = ["latest-fight.mp4", "previous-1.mp4", "previous-2.mp4"]
    for index, clip in enumerate(clips):
        assert int(clip.get("queue_slot", -1)) == index
        assert str(clip.get("video_url", "")).endswith(expected_names[index])
        assert clip.get("p1", {}).get("character")
        assert clip.get("p2", {}).get("character")
        assert float(clip.get("duration_seconds", 0)) > 0

    current = clips[0]
    assert 45.0 < float(current["duration_seconds"]) < 100.0
    assert int(current.get("round_count", 0)) == 6
    assert current.get("policy_pixel_access") is False

    timeline = current.get("activity_timeline") or {}
    p1_timeline = timeline.get("p1") or []
    p2_timeline = timeline.get("p2") or []
    assert p1_timeline and p2_timeline
    assert len(p1_timeline) == len(p2_timeline)
    assert len(p1_timeline) >= 50, len(p1_timeline)
    for side in (p1_timeline, p2_timeline):
        assert all(int(row.get("total_spikes", 0)) >= 0 for row in side)
        times = [float(row["t_seconds"]) for row in side]
        assert times == sorted(times)
        assert 0 <= times[0] <= times[-1] <= float(current["duration_seconds"])

    morphology = current.get("morphology") or {}
    assert morphology.get("policy_access") is False
    assert morphology.get("coordinate_space") == "MaleCNS EM"
    assert morphology.get("coordinate_units") == "8 nm"
    assert morphology.get("projection") == "x-z"
    for side in ("p1", "p2"):
        neurons = (morphology.get("sides") or {}).get(side) or []
        assert neurons, side
        assert len(neurons) <= 6
        for neuron in neurons:
            morph = neuron.get("morphology") or {}
            assert int(neuron.get("body_id")) == int(morph.get("body_id"))
            segments = morph.get("segments") or []
            assert segments
            assert len(segments) <= 180
    assert not (morphology.get("failed_body_ids") or {}), morphology.get("failed_body_ids")

    assert video.get("mode") == "official-fightingice-screendata-spectator"
    assert video.get("policy_pixel_access") is False
    assert int(video.get("width", 0)) == 960
    assert int(video.get("height", 0)) == 640
    assert int(video.get("fps", 0)) == 10
    assert int(video.get("rounds", 0)) == 6
    assert 45.0 < float(video.get("duration_seconds", 0)) < 100.0

    result = {
        "status": "PASS",
        "clips": len(clips),
        "current_clip_id": queue["current_clip_id"],
        "duration_seconds": current["duration_seconds"],
        "p1_activity_samples": len(p1_timeline),
        "p2_activity_samples": len(p2_timeline),
        "p1_morphologies": len(morphology["sides"]["p1"]),
        "p2_morphologies": len(morphology["sides"]["p2"]),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
