#!/usr/bin/env python3
"""Attach spectator-only released MaleCNS morphology to the current queue clip."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--morphology", type=Path, required=True)
    args = p.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    morphology = json.loads(args.morphology.read_text(encoding="utf-8"))
    clips = queue.get("clips") or []
    current = queue.get("current_clip_id")
    target = next((clip for clip in clips if clip.get("clip_id") == current), None)
    if target is None:
        raise ValueError("current clip not found in queue")
    target["morphology"] = morphology
    queue["schema_version"] = max(int(queue.get("schema_version", 1)), 4)
    args.queue.write_text(json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "clip_id": current,
        "p1_morphologies": len((morphology.get("sides") or {}).get("p1") or []),
        "p2_morphologies": len((morphology.get("sides") or {}).get("p2") or []),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
