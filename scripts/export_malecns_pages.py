#!/usr/bin/env python3
"""Export canonical MaleCNS FightingICE artifacts to compact GitHub Pages JSON."""
from __future__ import annotations

import argparse
import collections
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path

ACTION_NAMES = {
    0: "NEUTRAL", 1: "FORWARD", 2: "BACKWARD", 3: "UP",
    4: "DOWN", 5: "A", 6: "B", 7: "C",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_coordinates(path: Path | None) -> tuple[dict[int, tuple[float, float, float]], dict | None]:
    if path is None or not path.is_file():
        return {}, None
    coords: dict[int, tuple[float, float, float]] = {}
    bounds = {a: [float("inf"), float("-inf")] for a in ("x", "y", "z")}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"bodyId", "pos_x", "pos_y", "pos_z"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"coordinate index missing columns: {required - set(reader.fieldnames or [])}")
        for row in reader:
            body = int(row["bodyId"])
            xyz = (float(row["pos_x"]), float(row["pos_y"]), float(row["pos_z"]))
            coords[body] = xyz
            for axis, value in zip(("x", "y", "z"), xyz):
                bounds[axis][0] = min(bounds[axis][0], value)
                bounds[axis][1] = max(bounds[axis][1], value)
    if not coords:
        raise ValueError("coordinate index is empty")
    return coords, {
        "source": "MaleCNS v1.0 released annotation coordinates",
        "policy_access": False,
        "projection": "XY",
        "bounds": {k: {"min": v[0], "max": v[1]} for k, v in bounds.items()},
    }


def find_runs(root: Path) -> list[dict]:
    runs = []
    for status_path in root.rglob("status.json"):
        run_dir = status_path.parent
        p1, p2 = run_dir / "p1.jsonl", run_dir / "p2.jsonl"
        if not p1.is_file() or not p2.is_file():
            continue
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("canonical") is not True:
            continue
        chars, seeds = status.get("characters") or [], status.get("seeds") or []
        if len(chars) != 2 or len(seeds) != 2:
            continue
        rounds1, rounds2 = read_jsonl(p1), read_jsonl(p2)
        if len(rounds1) != len(rounds2) or not rounds1:
            continue
        runs.append({
            "dir": run_dir, "status": status,
            "characters": [str(x) for x in chars], "seeds": [int(x) for x in seeds],
            "p1": rounds1, "p2": rounds2,
            "run_id": str(status.get("run_id", run_dir.name)),
        })
    return runs


def pair_key(run: dict) -> tuple:
    return tuple(sorted((run["characters"][i], run["seeds"][i]) for i in range(2)))


def reward_nonzero(round_row: dict) -> bool:
    return float(round_row.get("outcome_reward", 0.0)) != 0.0


def summarize(runs: list[dict]) -> tuple[list[dict], dict]:
    reps = {}
    for run in sorted(runs, key=lambda r: r["run_id"]):
        reps.setdefault(pair_key(run), run)
    representative = list(reps.values())
    raw_rounds = sum(len(r["p1"]) for r in runs)
    independent_rounds = sum(len(r["p1"]) for r in representative)
    raw_nonzero = sum(reward_nonzero(x) for r in runs for x in r["p1"])
    independent_nonzero = sum(reward_nonzero(x) for r in representative for x in r["p1"])

    actions = collections.Counter()
    character_stats = collections.defaultdict(lambda: {
        "rounds": 0, "wins": 0, "losses": 0, "draws": 0,
        "decisions": 0, "actions": collections.Counter(),
    })
    for run in representative:
        for side in (0, 1):
            character = run["characters"][side]
            rows = run["p1"] if side == 0 else run["p2"]
            stats = character_stats[character]
            for row in rows:
                stats["rounds"] += 1
                reward = float(row.get("outcome_reward", 0.0))
                if reward > 0: stats["wins"] += 1
                elif reward < 0: stats["losses"] += 1
                else: stats["draws"] += 1
                for transition in row.get("transitions", []):
                    action = int(transition["action"])
                    actions[action] += 1
                    stats["actions"][action] += 1
                    stats["decisions"] += 1

    total_decisions = sum(actions.values())
    metrics = {
        "raw_runs": len(runs),
        "independent_seed_pairings": len(representative),
        "raw_rounds": raw_rounds,
        "independent_rounds": independent_rounds,
        "raw_nonzero_reward_rounds": raw_nonzero,
        "independent_nonzero_reward_rounds": independent_nonzero,
        "independent_nonzero_reward_rate": independent_nonzero / independent_rounds if independent_rounds else 0.0,
        "total_decisions": total_decisions,
        "action_counts": {ACTION_NAMES.get(k, str(k)): int(v) for k, v in sorted(actions.items())},
        "action_rates": {ACTION_NAMES.get(k, str(k)): (v / total_decisions if total_decisions else 0.0) for k, v in sorted(actions.items())},
        "characters": {
            character: {
                "rounds": int(value["rounds"]), "wins": int(value["wins"]),
                "losses": int(value["losses"]), "draws": int(value["draws"]),
                "decisions": int(value["decisions"]),
                "action_counts": {ACTION_NAMES.get(k, str(k)): int(n) for k, n in sorted(value["actions"].items())},
            }
            for character, value in sorted(character_stats.items())
        },
    }
    return representative, metrics


def compact_brain(transition: dict, coordinates: dict[int, tuple[float, float, float]]) -> dict:
    brain = transition.get("brain") or {}
    group_counts = brain.get("group_spike_counts") or {}
    top = brain.get("top_spike_bodies") or []
    max_top = max([int(x[1]) for x in top], default=1)
    top_rows = []
    for row in top[:12]:
        body, spikes = int(row[0]), int(row[1])
        item = {"body_id": body, "spikes": spikes, "relative": float(spikes) / max_top}
        if body in coordinates:
            x, y, z = coordinates[body]
            item["position"] = {"x": x, "y": y, "z": z}
        top_rows.append(item)
    return {
        "total_spikes": int(brain.get("total_spikes", 0)),
        "group_spike_counts": {str(k): int(v) for k, v in group_counts.items()},
        "top_bodies": top_rows,
        "membrane_summary": brain.get("membrane_summary") or {},
    }


def build_replay(representative: list[dict], coordinates: dict[int, tuple[float, float, float]], coordinate_space: dict | None) -> dict:
    candidate = None
    for run in representative:
        for idx, (round1, round2) in enumerate(zip(run["p1"], run["p2"])):
            if reward_nonzero(round1):
                candidate = (run, idx, round1, round2)
                break
        if candidate: break
    if candidate is None:
        run = representative[-1]
        idx = len(run["p1"]) - 1
        candidate = (run, idx, run["p1"][idx], run["p2"][idx])

    run, idx, round1, round2 = candidate
    p2_by_frame = {int(t["frame"]): t for t in round2.get("transitions", [])}
    frames = []
    for t1 in round1.get("transitions", []):
        frame = int(t1["frame"])
        t2 = p2_by_frame.get(frame)
        if t2 is None: continue
        display = t1.get("display") or {}
        d1, d2 = display.get("p1") or {}, display.get("p2") or {}
        frames.append({
            "frame": frame,
            "p1": {**{k: d1.get(k) for k in ("hp", "x", "y", "speed_x", "speed_y")}, "action": ACTION_NAMES.get(int(t1["action"]), str(t1["action"])), "brain": compact_brain(t1, coordinates)},
            "p2": {**{k: d2.get(k) for k in ("hp", "x", "y", "speed_x", "speed_y")}, "action": ACTION_NAMES.get(int(t2["action"]), str(t2["action"])), "brain": compact_brain(t2, coordinates)},
        })

    remaining_hps = round1.get("remaining_hps", [None, None])
    reward = float(round1.get("outcome_reward", 0.0))
    winner = run["characters"][0] if reward > 0 else run["characters"][1] if reward < 0 else "DRAW"
    return {
        "schema_version": 2,
        "canonical_model": "MaleCNS v1.0 + pinned Shiu LIF",
        "run_id": run["run_id"], "round_ordinal": idx + 1,
        "p1": {"character": run["characters"][0], "seed": run["seeds"][0]},
        "p2": {"character": run["characters"][1], "seed": run["seeds"][1]},
        "result": {"remaining_hps": remaining_hps, "winner": winner, "p1_reward": reward, "p2_reward": -reward},
        "coordinate_space": coordinate_space,
        "frames": frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--site-data", type=Path, required=True)
    parser.add_argument("--coordinates", type=Path)
    parser.add_argument("--run-url")
    parser.add_argument("--updated-at")
    parser.add_argument("--history-limit", type=int, default=200)
    args = parser.parse_args()

    runs = find_runs(args.artifacts_root)
    if not runs: raise SystemExit("No canonical run artifacts found")
    coordinates, coordinate_space = load_coordinates(args.coordinates)
    representative, metrics = summarize(runs)
    replay = build_replay(representative, coordinates, coordinate_space)

    args.site_data.mkdir(parents=True, exist_ok=True)
    status_path = args.site_data / "status.json"
    previous = {}
    if status_path.is_file():
        try: previous = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception: previous = {}
    history = list(previous.get("history") or [])
    updated_at = args.updated_at or datetime.now(timezone.utc).isoformat()
    history.append({
        "updated_at": updated_at, "source_run_url": args.run_url,
        "independent_rounds": metrics["independent_rounds"],
        "nonzero_reward_rounds": metrics["independent_nonzero_reward_rounds"],
        "nonzero_reward_rate": metrics["independent_nonzero_reward_rate"],
        "action_rates": metrics["action_rates"],
    })
    history = history[-args.history_limit:]

    status = {
        "schema_version": 4,
        "phase": "canonical-baseline-no-weight-updates",
        "updated_at": updated_at,
        "canonical_model": "MaleCNS v1.0 + pinned Shiu LIF",
        "randomness": "observation-driven Poisson sensory spikes; deterministic spike-count argmax readout",
        "reward_design": {"id": "R0-terminal-hp-sign", "win": 1.0, "draw": 0.0, "loss": -1.0, "learning_enabled": False},
        "source_run_url": args.run_url,
        "metrics": metrics,
        "spatial_visualization": {"available": coordinate_space is not None, "policy_access": False},
        "latest_match": {"replay_url": "./data/replay-latest.json", "run_id": replay["run_id"], "winner": replay["result"]["winner"]},
        "history": history,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.site_data / "replay-latest.json").write_text(json.dumps(replay, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "metrics": metrics, "replay": status["latest_match"], "coordinates": len(coordinates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
