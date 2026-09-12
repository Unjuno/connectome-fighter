#!/usr/bin/env python3
"""Tail LIVE decision JSONL and publish compact annotated neural activity."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import signal
import time
from typing import Any


def aggregate(rows: list[dict[str, Any]], field: str, value_field: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows:
        name = row.get(field)
        if not name:
            continue
        try:
            value = float(row.get(value_field, 0))
        except (TypeError, ValueError):
            continue
        counts[str(name)] += value
    return [
        {"name": name, "value": float(value)}
        for name, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
    ]


def compact_brain(event: dict[str, Any]) -> dict[str, Any]:
    brain = event.get("brain") or {}
    top = [row for row in (brain.get("top_spike_bodies_annotated") or []) if isinstance(row, dict)][:20]
    sensory = [row for row in (brain.get("sensory_drive_top_annotated") or []) if isinstance(row, dict)][:16]
    motor = [row for row in (brain.get("output_contributions_top_annotated") or []) if isinstance(row, dict)][:20]
    return {
        "decision_index": int(brain.get("trace_decision_index", 0)),
        "character": str(event.get("character") or brain.get("character") or ""),
        "round": int(event.get("round_id", 0)),
        "frame": int(event.get("frame", 0)),
        "top_bodies": top,
        "sensory_drive": sensory,
        "motor_contributors": motor,
        "neuromeres": aggregate(top, "soma_neuromere", "spikes"),
        "superclasses": aggregate(top, "superclass", "spikes"),
        "types": aggregate(top, "type", "spikes"),
        "interpretation_boundary": (
            "Region loads aggregate only the bounded top-spiking real body-ID sample from this decision window; "
            "they are not an all-neuron activity map or a biological functional assignment."
        ),
    }


def write_payload(path: Path, latest: dict[int, dict[str, Any]]) -> None:
    payload = {
        "schema_version": 1,
        "kind": "male-cns-live-anatomy-activity",
        "policy_access": False,
        "sides": {
            "p1": latest.get(1),
            "p2": latest.get(2),
        },
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jsonl", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stop = False

    def stopping(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, stopping)
    signal.signal(signal.SIGINT, stopping)

    latest: dict[int, dict[str, Any]] = {}
    offset = 0
    partial = ""
    while not stop:
        try:
            if args.jsonl.exists():
                size = args.jsonl.stat().st_size
                if size < offset:
                    offset = 0
                    partial = ""
                with args.jsonl.open("r", encoding="utf-8") as handle:
                    handle.seek(offset)
                    chunk = handle.read()
                    offset = handle.tell()
                if chunk:
                    partial += chunk
                    lines = partial.split("\n")
                    partial = lines.pop()
                    changed = False
                    for line in lines:
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if event.get("kind") != "decision":
                            continue
                        side = int(event.get("side", 0))
                        if side not in (1, 2):
                            continue
                        latest[side] = compact_brain(event)
                        changed = True
                    if changed:
                        write_payload(args.output, latest)
        except OSError:
            pass
        time.sleep(0.08)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
