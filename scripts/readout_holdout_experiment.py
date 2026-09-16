#!/usr/bin/env python3
"""Held-out real-game comparison of canonical vs EMA-residual MaleCNS readout.

This is a read-only control-contract experiment. It fixes the candidate checkpoint,
MaleCNS anatomy, Shiu dynamics, observation mapping, 20 ms neural window, 60-frame
action cadence and canonical ZEN opponent implementation. Only P1's project-defined
conversion from seven neural output-group counts to a FightingICE action changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tarfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
MODES = ("canonical", "ema-residual")
SEED_PAIRS = ((951101, 25101), (951211, 25211), (951307, 25307))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root", type=Path, required=True)
    p.add_argument("--source-archive", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout-seconds", type=int, default=1500)
    args = p.parse_args()
    if os.environ.get("CI") != "true" or os.environ.get("VERCEL"):
        p.error("standalone CI only")
    if not 300 <= args.timeout_seconds <= 1800:
        p.error("timeout must be 300..1800 seconds")

    runtime = args.runtime_root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + args.timeout_seconds
    result = {"status": "FAIL", "kind": "temporal-readout-heldout-v1", "strength_claim": False}
    try:
        manifest = json.loads((runtime / "manifest.json").read_text(encoding="utf-8"))
        if manifest["canonical_model"] != "MaleCNS v1.0 + pinned Shiu LIF":
            raise ValueError("canonical model mismatch")
        if manifest["learning_enabled"] is not False or manifest["policy_pixel_access"] is not False:
            raise ValueError("runtime policy boundary mismatch")
        interface = json.loads((runtime / "data/interface.json").read_text(encoding="utf-8"))
        if float(interface["decision"]["window_ms"]) != 20.0:
            raise ValueError("neural decision window changed")
        ref = runtime / (runtime / "runtime/python310.path").read_text().strip()
        bridge = runtime / (runtime / "runtime/python311.path").read_text().strip()

        source = out / "source"
        source.mkdir()
        with tarfile.open(args.source_archive) as archive:
            archive.extractall(source, filter="data")
        state = source / "state/GARNET.npz"
        meta = json.loads(state.with_suffix(".npz.json").read_text(encoding="utf-8"))
        if sha(state) != meta["state_sha256"] or meta["character"] != "GARNET" or meta["reward_id"] != "R2e-combat-v1":
            raise ValueError("candidate checkpoint identity mismatch")
        parent_sha = sha(state)

        env = dict(
            os.environ,
            PYTHONPATH=f"{ROOT/'src'}:{runtime/'runtime/site311'}",
            PATH=f"{runtime/'runtime/jre21/bin'}:{os.environ['PATH']}",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        wrapper = out / "reference-python"
        wrapper.write_text(
            "#!/bin/sh\nexport PYTHONPATH=" + shlex.quote(str(runtime / "runtime/site310")) + "\nexec " + shlex.quote(str(ref)) + " \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        adapter = out / "candidate-adapter"
        subprocess.run(
            [
                str(bridge), str(ROOT / "scripts/materialize_malecns_valence_adapter.py"),
                "--base-adapter", str(runtime / "data/malecns-shiu-strict-v1"),
                "--candidates", str(runtime / "data/malecns-valence-v1/kc_mbon_valence_candidates.parquet"),
                "--state", str(state), "--character", "GARNET",
                "--plasticity-config", str(ROOT / "configs/plasticity_combat_v1.json"),
                "--out", str(adapter),
            ],
            check=True, env=env, cwd=ROOT, timeout=180,
        )
        if sha(state) != parent_sha:
            raise RuntimeError("materialization changed source state")

        rows = []
        for seed_p1, seed_p2 in SEED_PAIRS:
            for mode in MODES:
                if time.monotonic() > deadline:
                    raise TimeoutError("overall held-out readout budget exhausted")
                name = f"seed-{seed_p1}-{seed_p2}-{mode}"
                game_log = out / f"{name}-game.log"
                with game_log.open("wb") as handle:
                    game = subprocess.Popen(
                        [
                            str(runtime / "runtime/jre21/bin/java"), "-cp",
                            "FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*",
                            "Main", "--headless-mode", "--pyftg-mode", "--input-sync",
                            "--limithp", "400", "400", "--port", "31415", "-r", "1", "-f", "3600",
                        ],
                        cwd=runtime / "fightingice", env=env, stdout=handle, stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                try:
                    for _ in range(120):
                        if game.poll() is not None:
                            raise RuntimeError(f"{name}: FightingICE exited before startup")
                        if "Socket server is started" in game_log.read_text(errors="replace"):
                            break
                        time.sleep(0.25)
                    else:
                        raise TimeoutError(f"{name}: FightingICE startup timeout")
                    timeout = max(1, min(360, int(deadline - time.monotonic())))
                    subprocess.run(
                        [
                            str(bridge), str(ROOT / "scripts/run_game_malecns_lif.py"),
                            "--host", "127.0.0.1", "--port", "31415",
                            "--character-p1", "GARNET", "--character-p2", "ZEN",
                            "--seed-p1", str(seed_p1), "--seed-p2", str(seed_p2),
                            "--reference-python", str(wrapper), "--reference-model", str(runtime / "shiu/model.py"),
                            "--adapter-dir", str(runtime / "data/malecns-shiu-strict-v1"),
                            "--adapter-dir-p1", str(adapter), "--interface", str(runtime / "data/interface.json"),
                            "--decision-interval", "60", "--readout-mode-p1", mode, "--readout-mode-p2", "canonical",
                            "--games", "1", "--expected-rounds", "1", "--timeout", str(timeout),
                            "--run-id", name, "--out", str(out / "matches"),
                        ],
                        check=True, env=env, cwd=ROOT, timeout=max(1, deadline - time.monotonic()),
                    )
                finally:
                    stop(game)

                folder = out / "matches" / name
                status = json.loads((folder / "status.json").read_text(encoding="utf-8"))
                expected_status = (
                    "COMPLETED_WITH_VALIDATED_CANONICAL_TRACES"
                    if mode == "canonical"
                    else "COMPLETED_WITH_VALIDATED_EXPERIMENTAL_READOUT_TRACES"
                )
                if status["status"] != expected_status:
                    raise RuntimeError(f"{name}: unexpected runner status {status['status']}")
                if status["readout_modes"] != [mode, "canonical"] or status["readout_game_state_used"] is not False:
                    raise RuntimeError(f"{name}: readout provenance mismatch")
                if status["learning_performed"] is not False or status["trace_trainable"] is not False:
                    raise RuntimeError(f"{name}: evaluation mutated learning boundary")
                if status["completed_rounds_per_agent"] != [1, 1]:
                    raise RuntimeError(f"{name}: incomplete round")
                trace = json.loads((folder / "p1.jsonl").read_text(encoding="utf-8").strip())
                hps = [max(0, int(v)) for v in trace["remaining_hps"]]
                transitions = trace["transitions"]
                if not transitions or (trace["elapsed_frame"] != 3600 and min(hps) != 0):
                    raise RuntimeError(f"{name}: invalid terminal record")
                initial = transitions[0]["display"]
                dealt = max(0, int(initial["p2"]["hp"]) - hps[1])
                taken = max(0, int(initial["p1"]["hp"]) - hps[0])
                outcome = float(trace["outcome_reward"])
                hp_advantage = (hps[0] - hps[1]) / 400.0
                combat_score = outcome + 0.02 * hp_advantage
                row = {
                    "seed_p1": seed_p1, "seed_p2": seed_p2, "readout_mode": mode,
                    "p1_hp": hps[0], "p2_hp": hps[1], "damage_dealt_hp": dealt, "damage_taken_hp": taken,
                    "outcome": outcome, "combat_score": combat_score, "elapsed_frame": int(trace["elapsed_frame"]),
                    "decision_count": len(transitions),
                    "requested_action_counts": dict(Counter(str(t["action"]) for t in transitions)),
                    "source_state_sha256": parent_sha,
                }
                rows.append(row)
                write(out / "partial-results.json", rows)
                if sha(state) != parent_sha:
                    raise RuntimeError("held-out readout run changed candidate state")

        pairs = []
        for seed_p1, seed_p2 in SEED_PAIRS:
            canonical = next(r for r in rows if r["seed_p1"] == seed_p1 and r["readout_mode"] == "canonical")
            ema = next(r for r in rows if r["seed_p1"] == seed_p1 and r["readout_mode"] == "ema-residual")
            pairs.append({
                "seed_p1": seed_p1, "seed_p2": seed_p2,
                "combat_score_delta": ema["combat_score"] - canonical["combat_score"],
                "net_hp_delta": (ema["p1_hp"] - ema["p2_hp"]) - (canonical["p1_hp"] - canonical["p2_hp"]),
                "damage_dealt_delta": ema["damage_dealt_hp"] - canonical["damage_dealt_hp"],
                "damage_taken_delta": ema["damage_taken_hp"] - canonical["damage_taken_hp"],
            })
        canonical_rows = [r for r in rows if r["readout_mode"] == "canonical"]
        ema_rows = [r for r in rows if r["readout_mode"] == "ema-residual"]
        positive_pairs = sum(p["combat_score_delta"] > 0 for p in pairs)
        selection = {
            "positive_combat_score_pairs": positive_pairs,
            "pair_count": len(pairs),
            "canonical_total_damage_dealt_hp": sum(r["damage_dealt_hp"] for r in canonical_rows),
            "ema_total_damage_dealt_hp": sum(r["damage_dealt_hp"] for r in ema_rows),
            "canonical_total_net_hp": sum(r["p1_hp"] - r["p2_hp"] for r in canonical_rows),
            "ema_total_net_hp": sum(r["p1_hp"] - r["p2_hp"] for r in ema_rows),
        }
        selection["candidate_for_training_control_contract"] = bool(
            selection["positive_combat_score_pairs"] >= 2
            and selection["ema_total_damage_dealt_hp"] > selection["canonical_total_damage_dealt_hp"]
            and selection["ema_total_net_hp"] > selection["canonical_total_net_hp"]
        )
        result = {
            "status": "PASS", "kind": "temporal-readout-heldout-v1",
            "candidate_generation": int(meta["generation"]), "candidate_state_sha256": parent_sha,
            "reward_id": meta["reward_id"], "tested_at": datetime.now(timezone.utc).isoformat(),
            "decision_interval_frames": 60, "fixed_neural_window_ms": 20.0,
            "modes": list(MODES), "seed_pairs": [list(x) for x in SEED_PAIRS],
            "learning_performed": False, "weights_changed": False, "readout_game_state_used": False,
            "policy_pixel_access": False, "synthetic_neural_fixture": False,
            "rows": rows, "paired_deltas": pairs, "selection": selection,
            "actual_pipeline_seconds": time.monotonic() - started, "strength_claim": False,
            "interpretation_boundary": (
                "Three held-out seed pairs test whether EMA-residual changes fighting outcomes relative to the canonical "
                "absolute-spike argmax under the same checkpoint and opponent implementation. This is control-interface "
                "selection evidence, not a general strength or biological-validity claim."
            ),
        }
        write(out / "result.json", result)
        return 0
    except Exception:
        result["error"] = traceback.format_exc()
        result["actual_pipeline_seconds"] = time.monotonic() - started
        write(out / "result.json", result)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
