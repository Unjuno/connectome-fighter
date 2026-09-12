#!/usr/bin/env python3
"""Drive the upstream FlyBody MuJoCo fruit fly from live MaleCNS activity.

This is a spectator-only embodied readout.  It consumes the same decision JSONL
as the arena telemetry, derives a bounded motor command from real annotated
MaleCNS output bodies, steps TuragaLab/flybody's actual MuJoCo body, and writes
latest PNG/state files atomically.  FightingICE x/y/action are not used to move
the FlyBody model.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectome_fighter.flybody_neural_adapter import NeuralFlyCommand, flybody_action, neural_fly_command
from connectome_fighter.rgb_png import encode_rgb_png

FLYBODY_UPSTREAM = "TuragaLab/flybody"
FLYBODY_COMMIT = "d015e9bfe441bd90ae431bac24c55cb74bdbce26"


def atomic_bytes(path: Path, payload: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


class FlyBodySide:
    def __init__(self, *, seed: int, width: int, height: int) -> None:
        # dm_control/MuJoCo must see the backend choice before import. OSMesa is
        # the default because the shared Vercel Sandbox has no GPU/display.
        os.environ.setdefault("MUJOCO_GL", "osmesa")
        from flybody.fly_envs import template_task

        self.env = template_task(
            random_state=np.random.RandomState(seed),
            force_actuators=False,
            disable_wings=True,
            joint_filter=0.01,
            adhesion_filter=0.007,
            time_limit=3600.0,
        )
        self.env.reset()
        spec = self.env.action_spec()
        self.names = str(spec.name or "").split()
        self.minimum = np.asarray(spec.minimum, dtype=float)
        self.maximum = np.asarray(spec.maximum, dtype=float)
        if len(self.names) != self.minimum.size:
            raise RuntimeError(f"FlyBody action-name/spec mismatch: {len(self.names)} != {self.minimum.size}")
        self.width = int(width)
        self.height = int(height)
        self.phase = 0.0
        self.command = neural_fly_command([])
        self.sim_steps = 0
        self.resets = 0

    @property
    def control_timestep(self) -> float:
        try:
            return float(self.env.task.control_timestep)
        except Exception:
            return 0.002

    def set_command(self, command: NeuralFlyCommand) -> None:
        self.command = command

    def advance(self, real_dt: float) -> None:
        dt = self.control_timestep
        # Keep the physics bounded on shared CPU while approaching wall-clock
        # stepping. The neural drive controls gait phase speed, not game x/y.
        # Zero motor drive therefore produces no active gait phase progression.
        steps = max(1, min(16, int(round(max(real_dt, dt) / dt))))
        sim_dt = max(dt, real_dt / steps)
        gait_hz = 6.0 * self.command.drive
        for _ in range(steps):
            self.phase = (self.phase + 2.0 * math.pi * gait_hz * sim_dt) % (2.0 * math.pi)
            action = flybody_action(
                self.names,
                self.minimum,
                self.maximum,
                self.command,
                self.phase,
            )
            timestep = self.env.step(action)
            self.sim_steps += 1
            if timestep.last():
                self.env.reset()
                self.resets += 1

    def render(self) -> np.ndarray:
        pixels = self.env.physics.render(height=self.height, width=self.width, camera_id=1)
        pixels = np.asarray(pixels, dtype=np.uint8)
        if pixels.shape != (self.height, self.width, 3):
            raise RuntimeError(f"unexpected FlyBody render shape: {pixels.shape}")
        return np.ascontiguousarray(pixels)

    def physical_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "sim_steps": self.sim_steps,
            "resets": self.resets,
            "action_dimension": len(self.names),
            "gait_phase_rad": float(self.phase),
        }
        try:
            body_id = self.env.physics.model.name2id("walker/thorax", "body")
            state["thorax_world_position"] = [float(v) for v in self.env.physics.data.xpos[body_id]]
        except Exception:
            state["thorax_world_position"] = None
        return state


def compact_command(event: dict[str, Any] | None) -> NeuralFlyCommand:
    brain = (event or {}).get("brain") or {}
    rows = brain.get("output_contributions_top_annotated") or []
    return neural_fly_command(row for row in rows if isinstance(row, dict))


def event_identity(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    brain = event.get("brain") or {}
    return {
        "round": int(event.get("round_id", 0)),
        "frame": int(event.get("frame", 0)),
        "decision_index": int(brain.get("trace_decision_index", 0)),
        "character": str(event.get("character") or brain.get("character") or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--p1-output", type=Path, required=True)
    parser.add_argument("--p2-output", type=Path, required=True)
    parser.add_argument("--state-output", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    args = parser.parse_args()
    if args.fps <= 0 or args.width < 160 or args.height < 120:
        parser.error("invalid FlyBody fps/render dimensions")
    for path in (args.p1_output, args.p2_output, args.state_output):
        path.parent.mkdir(parents=True, exist_ok=True)

    stop = False
    def stopping(*_args: object) -> None:
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, stopping)
    signal.signal(signal.SIGINT, stopping)

    sides = {
        1: FlyBodySide(seed=7101, width=args.width, height=args.height),
        2: FlyBodySide(seed=7202, width=args.width, height=args.height),
    }
    latest: dict[int, dict[str, Any]] = {}
    offset = 0
    partial = ""
    last_tick = time.monotonic()
    last_publish = 0.0
    frame_count = 0

    while not stop:
        try:
            if args.jsonl.exists():
                size = args.jsonl.stat().st_size
                if size < offset:
                    offset = 0
                    partial = ""
                    latest.clear()
                with args.jsonl.open("r", encoding="utf-8") as handle:
                    handle.seek(offset)
                    chunk = handle.read()
                    offset = handle.tell()
                if chunk:
                    partial += chunk
                    lines = partial.split("\n")
                    partial = lines.pop()
                    changed: set[int] = set()
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
                        latest[side] = event
                        changed.add(side)
                    for side in changed:
                        sides[side].set_command(compact_command(latest.get(side)))
        except OSError:
            pass

        now = time.monotonic()
        real_dt = min(0.1, max(0.001, now - last_tick))
        last_tick = now
        for simulator in sides.values():
            simulator.advance(real_dt)

        if now - last_publish >= 1.0 / args.fps:
            p1 = sides[1].render()
            p2 = sides[2].render()
            atomic_bytes(args.p1_output, encode_rgb_png(p1))
            atomic_bytes(args.p2_output, encode_rgb_png(p2))
            frame_count += 1
            payload = {
                "schema_version": 1,
                "kind": "malecns-flybody-live-physics",
                "policy_access": False,
                "game_telemetry_position_used": False,
                "mujoco_gl": os.environ.get("MUJOCO_GL", "osmesa"),
                "upstream": {"repository": FLYBODY_UPSTREAM, "commit": FLYBODY_COMMIT},
                "adapter": "malecns-annotated-motor-to-flybody-tripod-v1",
                "render": {"width": args.width, "height": args.height, "frames": frame_count, "fps_target": args.fps},
                "sides": {
                    "p1": {
                        "decision": event_identity(latest.get(1)),
                        "neural_command": sides[1].command.to_json(),
                        "physics": sides[1].physical_state(),
                    },
                    "p2": {
                        "decision": event_identity(latest.get(2)),
                        "neural_command": sides[2].command.to_json(),
                        "physics": sides[2].physical_state(),
                    },
                },
                "interpretation_boundary": (
                    "The rendered body and dynamics are TuragaLab/flybody MuJoCo physics. "
                    "MaleCNS body activity is real; the neural-to-actuator adapter is project-defined "
                    "and is not claimed as a known biological motor innervation map."
                ),
            }
            atomic_json(args.state_output, payload)
            last_publish = now
        time.sleep(0.005)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
