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
import hashlib
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

from connectome_fighter.flybody_neural_adapter import ADAPTER_ID, NeuralFlyCommand, flybody_action, neural_fly_command
from connectome_fighter.rgb_png import encode_rgb_png

FLYBODY_UPSTREAM = "TuragaLab/flybody"
FLYBODY_COMMIT = "d015e9bfe441bd90ae431bac24c55cb74bdbce26"
PUBLISHER_ID = "malecns-flybody-publisher-v2"


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
        self.pending_time_seconds = 0.0
        self.sim_time_seconds = 0.0
        self.dropped_time_seconds = 0.0

    @property
    def control_timestep(self) -> float:
        dt = float(self.env.task.control_timestep)
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("FlyBody control_timestep must be finite and positive")
        return dt

    def set_command(self, command: NeuralFlyCommand) -> None:
        # Also validate direct callers, not only JSONL ingestion.
        values = (command.drive, command.left_drive, command.right_drive,
                  command.t1_drive, command.t2_drive, command.t3_drive,
                  command.descending_drive)
        if (not all(math.isfinite(v) and 0 <= v <= 1 for v in values)
                or not math.isfinite(command.lateral_bias)
                or abs(command.lateral_bias) > 1
                or not math.isfinite(command.source_spikes)
                or command.source_spikes < 0):
            raise ValueError("invalid or non-finite neural command")
        self.command = command

    def advance(self, real_dt: float) -> None:
        if not math.isfinite(real_dt) or real_dt < 0:
            raise ValueError("elapsed time must be finite and non-negative")
        dt = self.control_timestep
        available = self.pending_time_seconds + real_dt
        # Bounded slow-motion spectator: drop excess wall time explicitly, rather
        # than advancing the gait phase faster than MuJoCo's actual step clock.
        budget = min(available, 16 * dt)
        self.dropped_time_seconds += available - budget
        steps = min(16, int(math.floor(budget / dt + 1e-9)))
        self.pending_time_seconds = max(0.0, budget - steps * dt)
        gait_hz = 6.0 * self.command.drive
        for _ in range(steps):
            phase = (self.phase + 2.0 * math.pi * gait_hz * dt) % (2.0 * math.pi)
            action = flybody_action(
                self.names, self.minimum, self.maximum, self.command, phase,
            )
            timestep = self.env.step(action)
            self.phase = phase
            self.sim_steps += 1
            self.sim_time_seconds += dt
            if timestep.last():
                self.env.reset()
                self.phase = 0.0
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
            "control_timestep_seconds": self.control_timestep,
            "sim_time_seconds": self.sim_time_seconds,
            "pending_time_seconds": self.pending_time_seconds,
            "dropped_time_seconds": self.dropped_time_seconds,
            "timebase": "executed-physics-control-steps",
        }
        try:
            body_id = self.env.physics.model.name2id("walker/thorax", "body")
            state["thorax_world_position"] = [float(v) for v in self.env.physics.data.xpos[body_id]]
        except Exception:
            state["thorax_world_position"] = None
        return state


def compact_command(event: dict[str, Any] | None) -> NeuralFlyCommand:
    brain = event.get("brain") if isinstance(event, dict) else None
    rows = brain.get("output_contributions_top_annotated") if isinstance(brain, dict) else None
    if not isinstance(rows, list):
        return neural_fly_command([])
    clean = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            spikes = float(row.get("spikes", 0))
            raw_id = row.get("body_id", 0)
            body_id = int(raw_id)
            if isinstance(raw_id, (bool, float)) or not math.isfinite(spikes) or spikes <= 0 or body_id <= 0:
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        clean.append(dict(row, body_id=body_id, spikes=spikes))
    command = neural_fly_command(clean)
    # Individually finite numbers can still overflow in the aggregate.
    values = (command.drive, command.left_drive, command.right_drive,
              command.t1_drive, command.t2_drive, command.t3_drive,
              command.descending_drive, command.lateral_bias, command.source_spikes)
    return command if all(math.isfinite(v) for v in values) else neural_fly_command([])


def event_identity(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(event, dict) or not isinstance(event.get("brain"), dict):
        return None
    brain = event["brain"]
    values = (event.get("round_id"), event.get("frame"), brain.get("trace_decision_index"))
    # Missing or malformed identity must not become a plausible all-zero tuple.
    if any(type(v) is not int or v < 0 for v in values):
        return None
    return {
        "round": values[0], "frame": values[1], "decision_index": values[2],
        "character": str(event.get("character") or brain.get("character") or ""),
    }


class DecisionFeed:
    """Bounded JSONL reader; never retain a command across an observed log reset.

    Freshness is time since local receipt, not a claim about source event time.
    Only the newest accepted decision per side is retained (not lossless replay).
    ``start_at_end`` is used by the live publisher so content left by an older
    session cannot become a fresh motor command merely because the process was
    restarted. After truncation/replacement, the same tail-from-now rule is
    applied before accepting newly appended decisions.
    """

    MAX_READ_BYTES = 4 * 1024 * 1024
    MAX_LINE_BYTES = 1024 * 1024

    def __init__(self, path: Path, *, stale_after_seconds: float = 30.0, start_at_end: bool = False) -> None:
        if not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be finite and positive")
        self.path = path
        self.stale_after_seconds = stale_after_seconds
        self.start_at_end = bool(start_at_end)
        self._needs_tail_init = self.start_at_end
        self.latest: dict[int, dict[str, Any]] = {}
        self.received_at: dict[int, float] = {}
        self.offset = 0
        self.partial = b""
        self.file_id: tuple[int, int] | None = None
        self.discarding = False
        self.epoch = 0
        self.rejected_records = 0

    def _reset(self) -> None:
        self.latest.clear()
        self.received_at.clear()
        self.offset = 0
        self.partial = b""
        self.discarding = False
        if self.start_at_end:
            self._needs_tail_init = True
        self.epoch += 1

    def poll(self, now: float) -> None:
        if not math.isfinite(now):
            raise ValueError("receipt clock must be finite")
        try:
            with self.path.open("rb") as handle:
                stat = os.fstat(handle.fileno())
                identity = (stat.st_dev, stat.st_ino)
                if (self.file_id is not None and identity != self.file_id) or stat.st_size < self.offset:
                    self._reset()
                self.file_id = identity
                if self._needs_tail_init:
                    self.offset = stat.st_size
                    self.partial = b""
                    self.discarding = False
                    self._needs_tail_init = False
                    return
                handle.seek(self.offset)
                chunk = handle.read(self.MAX_READ_BYTES)
                self.offset = handle.tell()
        except OSError:
            if self.file_id is not None or self.latest:
                self._reset()
            self.file_id = None
            return
        if self.discarding:
            boundary = chunk.find(b"\n")
            if boundary < 0:
                return
            chunk = chunk[boundary + 1:]
            self.discarding = False
        lines = (self.partial + chunk).split(b"\n")
        self.partial = lines.pop()
        if len(self.partial) > self.MAX_LINE_BYTES:
            self.partial = b""
            self.discarding = True
            self.rejected_records += 1
        for line in lines:
            if not line.strip():
                continue
            if len(line) > self.MAX_LINE_BYTES:
                self.rejected_records += 1
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
                self.rejected_records += 1
                continue
            if not isinstance(event, dict) or event.get("kind") != "decision":
                continue
            side = event.get("side")
            identity = event_identity(event)
            if type(side) is not int or side not in (1, 2) or identity is None:
                self.rejected_records += 1
                continue
            old = event_identity(self.latest.get(side))
            if old is not None and (
                identity["round"] < old["round"] or
                (identity["round"] == old["round"] and (
                    identity["frame"] < old["frame"] or
                    identity["decision_index"] <= old["decision_index"]
                ))
            ):
                self.rejected_records += 1
                continue
            self.latest[side] = event
            self.received_at[side] = now

    def state(self, side: int, now: float) -> dict[str, Any]:
        age = max(0.0, now - self.received_at[side]) if side in self.received_at else None
        fresh = age is not None and age < self.stale_after_seconds
        return {
            "input_status": "fresh" if fresh else "stale" if age is not None else "missing",
            "input_age_seconds": age,
            "input_epoch": self.epoch,
            "decision": event_identity(self.latest.get(side)) if fresh else None,
        }

    def command(self, side: int, now: float) -> NeuralFlyCommand:
        if self.state(side, now)["input_status"] != "fresh":
            return neural_fly_command([])
        return compact_command(self.latest.get(side))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--p1-output", type=Path, required=True)
    parser.add_argument("--p2-output", type=Path, required=True)
    parser.add_argument("--state-output", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--stale-after-sec", type=float, default=30.0)
    args = parser.parse_args()
    if not math.isfinite(args.fps) or args.fps <= 0 or args.width < 160 or args.height < 120:
        parser.error("invalid FlyBody fps/render dimensions")
    if not math.isfinite(args.stale_after_sec) or args.stale_after_sec <= 0:
        parser.error("stale-after-sec must be finite and positive")
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
    feed = DecisionFeed(args.jsonl, stale_after_seconds=args.stale_after_sec, start_at_end=True)
    last_tick = time.monotonic()
    last_publish = 0.0
    frame_count = 0

    while not stop:
        now = time.monotonic()
        feed.poll(now)
        real_dt = max(0.0, now - last_tick)
        last_tick = now
        for side, simulator in sides.items():
            simulator.set_command(feed.command(side, now))
            simulator.advance(real_dt)

        if now - last_publish >= 1.0 / args.fps:
            p1 = sides[1].render()
            p2 = sides[2].render()
            png1, png2 = encode_rgb_png(p1), encode_rgb_png(p2)
            atomic_bytes(args.p1_output, png1)
            atomic_bytes(args.p2_output, png2)
            frame_count += 1
            payload = {
                "schema_version": 2,
                "publisher": PUBLISHER_ID,
                "stale_after_seconds": args.stale_after_sec,
                "rejected_input_records": feed.rejected_records,
                "kind": "malecns-flybody-live-physics",
                "policy_access": False,
                "game_telemetry_position_used": False,
                "mujoco_gl": os.environ.get("MUJOCO_GL", "osmesa"),
                "upstream": {"repository": FLYBODY_UPSTREAM, "commit": FLYBODY_COMMIT},
                "adapter": ADAPTER_ID,
                "render": {"width": args.width, "height": args.height, "frames": frame_count, "fps_target": args.fps},
                "sides": {
                    "p1": {
                        **feed.state(1, now),
                        "png_sha256": hashlib.sha256(png1).hexdigest(),
                        "neural_command": sides[1].command.to_json(),
                        "physics": sides[1].physical_state(),
                    },
                    "p2": {
                        **feed.state(2, now),
                        "png_sha256": hashlib.sha256(png2).hexdigest(),
                        "neural_command": sides[2].command.to_json(),
                        "physics": sides[2].physical_state(),
                    },
                },
                "interpretation_boundary": (
                    "The rendered body and dynamics are TuragaLab/flybody MuJoCo physics. "
                    "MaleCNS body activity is real; the neural-to-actuator adapter is project-defined "
                    "and is not claimed as a known biological motor innervation map. "
                    "The decision identifies the held input, not lossless frame-locked replay. "
                    "Physics may run in slow motion under load; dropped wall time is reported. "
                    "PNG hashes bind state to image bytes, but readers must verify them."
                ),
            }
            atomic_json(args.state_output, payload)
            last_publish = now
        time.sleep(0.005)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
