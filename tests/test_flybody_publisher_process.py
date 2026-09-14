"""Real publisher subprocess lifecycle with engineering, not biological, inputs.

Runs actual FlyBody/MuJoCo/OSMesa and the production JSONL/PNG main loop.
No FightingICE, Vercel, training, or claims of native motor innervation.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pytest

os.environ.setdefault("MUJOCO_GL", "osmesa")
if os.environ.get("REQUIRE_FLYBODY_PHYSICS") == "1":
    import flybody  # noqa: F401
else:
    pytest.importorskip("flybody", reason="real FlyBody/MuJoCo is not installed")
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "d015e9bfe441bd90ae431bac24c55cb74bdbce26"
ADAPTER = "malecns-annotated-motor-to-flybody-tripod-v2"
SIDES = ("p1", "p2")


def event(side, decision, *, round_id=1):
    """Explicit synthetic body IDs; these are not MaleCNS recordings."""
    return {
        "kind": "decision", "side": side, "round_id": round_id,
        "frame": decision * 60, "character": "GARNET" if side == 1 else "ZEN",
        "brain": {
            "trace_decision_index": decision,
            "output_contributions_top_annotated": [
                {"body_id": side * 100 + 1, "spikes": 24, "superclass": "vnc_motor",
                 "soma_neuromere": "T1", "root_side": "L"},
                {"body_id": side * 100 + 2, "spikes": 10, "superclass": "vnc_motor",
                 "soma_neuromere": "T2", "root_side": "R"},
            ],
        },
    }


def write_events(path, decision, *, round_id=1, mode="a"):
    with path.open(mode, encoding="utf-8") as handle:
        for side in (1, 2):
            handle.write(json.dumps(event(side, decision, round_id=round_id)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class PublisherProcess:
    def __init__(self, directory, evidence):
        self.directory = directory
        self.evidence = evidence
        self.feed = directory / "decisions.jsonl"
        self.state_path = directory / "flybody.json"
        self.process = None
        self.log = None
        self.starts = 0
        self.samples = []

    def start(self):
        assert self.process is None
        for name in ("flybody.json", "p1.png", "p2.png"):
            (self.directory / name).unlink(missing_ok=True)
        self.starts += 1
        self.log_path = self.evidence / f"process-{self.starts}.log"
        self.log = self.log_path.open("wb")
        environment = os.environ.copy()
        environment["MUJOCO_GL"] = "osmesa"
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "scripts/run_live_flybody_publisher.py"),
             "--jsonl", str(self.feed), "--p1-output", str(self.directory / "p1.png"),
             "--p2-output", str(self.directory / "p2.png"), "--state-output", str(self.state_path),
             "--fps", "5", "--width", "160", "--height", "120", "--stale-after-sec", "2"],
            cwd=ROOT, env=environment, stdout=self.log, stderr=subprocess.STDOUT,
        )

    def stop(self, *, require_clean=False):
        if self.process is None:
            return
        process, self.process = self.process, None
        if process.poll() is None:
            process.terminate()
        try:
            returncode = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("publisher failed bounded SIGTERM shutdown")
        finally:
            self.log.close()
        if require_clean:
            assert returncode == 0, self.log_path.read_text(errors="replace")[-6000:]

    def await_snapshot(self, label, predicate, *, timeout=20):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            assert self.process.poll() is None, self.log_path.read_text(errors="replace")[-6000:]
            try:
                before = self.state_path.read_bytes()
                state = json.loads(before)
                images = {side: (self.directory / f"{side}.png").read_bytes() for side in SIDES}
                after = self.state_path.read_bytes()
            except (OSError, json.JSONDecodeError):
                time.sleep(0.02)
                continue
            # PNGs and state are separately atomic; retry a concurrent publication.
            if before != after or any(
                hashlib.sha256(images[side]).hexdigest() != state["sides"][side]["png_sha256"]
                for side in SIDES
            ):
                time.sleep(0.02)
                continue
            last = state
            if predicate(state):
                self.validate(state, images)
                (self.evidence / f"{label}.json").write_bytes(before)
                for side in SIDES:
                    (self.evidence / f"{label}-{side}.png").write_bytes(images[side])
                self.samples.append(label)
                print(f"publisher lifecycle: {label}; render={state['render']['frames']}", flush=True)
                return state
            time.sleep(0.02)
        raise AssertionError(f"deadline waiting for {label}; last={last}")

    @staticmethod
    def validate(state, images):
        assert state["schema_version"] == 2
        assert state["publisher"] == "malecns-flybody-publisher-v2"
        assert state["upstream"] == {"repository": "TuragaLab/flybody", "commit": UPSTREAM}
        assert state["adapter"] == ADAPTER
        assert state["mujoco_gl"] == "osmesa"
        assert state["policy_access"] is False
        assert state["game_telemetry_position_used"] is False
        for side in SIDES:
            sample = state["sides"][side]
            assert sample["neural_command"]["adapter"] == ADAPTER
            physics = sample["physics"]
            assert physics["action_dimension"] == 59
            assert physics["timebase"] == "executed-physics-control-steps"
            dt = physics["control_timestep_seconds"]
            assert np.isfinite(dt) and dt > 0
            # SI seconds on both sides: accumulated time equals executed steps * dt.
            assert physics["sim_time_seconds"] == pytest.approx(physics["sim_steps"] * dt, abs=1e-8)
            assert 0 <= physics["pending_time_seconds"] < dt + 1e-8
            assert physics["dropped_time_seconds"] >= 0
            assert np.isfinite(physics["gait_phase_rad"])
            with Image.open(io.BytesIO(images[side])) as image:
                assert image.size == (160, 120)
                pixels = np.asarray(image.convert("RGB"))
                assert float(pixels.std()) > 1.0


def all_status(state, status):
    return all(state["sides"][side]["input_status"] == status for side in SIDES)


def at_decision(state, decision, round_id=1):
    return all_status(state, "fresh") and all(
        state["sides"][side]["decision"]["decision_index"] == decision
        and state["sides"][side]["decision"]["round"] == round_id
        and state["sides"][side]["decision"]["frame"] == decision * 60
        for side in SIDES
    )


def assert_neutral(state):
    for side in SIDES:
        sample = state["sides"][side]
        assert sample["decision"] is None
        assert sample["neural_command"]["drive"] == 0
        assert sample["neural_command"]["source_body_ids"] == []


def test_real_process_input_expiry_rotation_restart_and_hash_bound_images(tmp_path):
    evidence = Path(os.environ.get("FLYBODY_EVIDENCE_DIR", str(tmp_path))) / "process-lifecycle"
    evidence.mkdir(parents=True, exist_ok=True)
    runner = PublisherProcess(tmp_path, evidence)
    # An old on-disk decision is not fresh just because the process starts.
    write_events(runner.feed, 99, round_id=9, mode="w")
    try:
        runner.start()
        initial = runner.await_snapshot("startup", lambda s: all_status(s, "missing"), timeout=60)
        assert_neutral(initial)
        write_events(runner.feed, 1)
        first = runner.await_snapshot("fresh-1", lambda s: at_decision(s, 1))
        write_events(runner.feed, 2)
        driven = runner.await_snapshot("fresh-2", lambda s: at_decision(s, 2) and all(
            s["sides"][side]["physics"]["sim_steps"] > first["sides"][side]["physics"]["sim_steps"]
            and s["sides"][side]["png_sha256"] != first["sides"][side]["png_sha256"]
            for side in SIDES
        ))
        for number, side in enumerate(SIDES, 1):
            assert driven["sides"][side]["neural_command"]["drive"] > 0
            assert driven["sides"][side]["neural_command"]["source_body_ids"] == [number * 100 + 1, number * 100 + 2]
        stale = runner.await_snapshot("stale", lambda s: all_status(s, "stale"))
        assert_neutral(stale)
        quiet = runner.await_snapshot("stale-later", lambda s: all_status(s, "stale") and
                                      s["render"]["frames"] >= stale["render"]["frames"] + 3)
        assert_neutral(quiet)
        for side in SIDES:
            previous, current = stale["sides"][side]["physics"], quiet["sides"][side]["physics"]
            assert current["sim_steps"] > previous["sim_steps"]
            assert current["resets"] == previous["resets"]
            assert current["gait_phase_rad"] == previous["gait_phase_rad"]
        # Zero active gait does not claim zero passive motion under gravity.
        replacement = tmp_path / "replacement.jsonl"
        write_events(replacement, 99, round_id=9, mode="w")
        replacement.replace(runner.feed)
        rotated = runner.await_snapshot("rotation", lambda s: all_status(s, "missing") and all(
            s["sides"][side]["input_epoch"] > quiet["sides"][side]["input_epoch"] for side in SIDES
        ))
        assert_neutral(rotated)
        write_events(runner.feed, 1, round_id=2)
        runner.await_snapshot("rotation-fresh", lambda s: at_decision(s, 1, 2))
        runner.stop(require_clean=True)
        runner.start()
        restarted = runner.await_snapshot("restart", lambda s: all_status(s, "missing"), timeout=60)
        assert_neutral(restarted)
        write_events(runner.feed, 1, round_id=3)
        runner.await_snapshot("restart-fresh", lambda s: at_decision(s, 1, 3))
        runner.stop(require_clean=True)
        (evidence / "result.json").write_text(json.dumps({
            "status": "PASS", "kind": "real-mujoco-publisher-process-engineering-test",
            "biological_inputs": False, "production_live_test": False, "real_fightingice": False,
            "upstream_commit": UPSTREAM, "render_backend": "osmesa", "adapter": ADAPTER,
            "publisher_seed_p1": 7101, "publisher_seed_p2": 7202,
            "render_width": 160, "render_height": 120, "fps_target": 5,
            "stale_after_seconds": 2, "process_starts": runner.starts,
            "samples": runner.samples, "python": sys.version,
            "interpretation_boundary": "Actual physics/process/PNG lifecycle; synthetic annotated neural inputs. Not production or biological proof.",
        }, indent=2, allow_nan=False) + "\n")
    finally:
        runner.stop()
