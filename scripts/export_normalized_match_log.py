#!/usr/bin/env python3
"""Export a rolling, normalized FightingICE match log for lightweight viewers.

The output intentionally excludes raw spike events, membrane vectors and replay
frames. Those stay in Actions artifacts. This file is the public/indexable match
ledger consumed by the Vercel viewer.
"""
from __future__ import annotations

import argparse
import collections
import json
from datetime import datetime, timezone
from pathlib import Path

ACTION_NAMES = {
    0: "NEUTRAL", 1: "FORWARD", 2: "BACKWARD", 3: "UP",
    4: "DOWN", 5: "A", 6: "B", 7: "C",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def action_counts(round_row: dict) -> dict[str, int]:
    counts = collections.Counter(int(t.get("action", 0)) for t in round_row.get("transitions", []))
    return {ACTION_NAMES.get(k, str(k)): int(v) for k, v in sorted(counts.items())}


def round_geometry(round_row: dict) -> dict:
    transitions = round_row.get("transitions") or []
    if not transitions:
        return {"initial_distance_px": None, "min_distance_px": None, "distance_reduction_px": None}
    distances = []
    for t in transitions:
        display = t.get("display") or {}
        p1, p2 = display.get("p1") or {}, display.get("p2") or {}
        try:
            distances.append(abs(float(p1["x"]) - float(p2["x"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not distances:
        return {"initial_distance_px": None, "min_distance_px": None, "distance_reduction_px": None}
    return {
        "initial_distance_px": distances[0],
        "min_distance_px": min(distances),
        "distance_reduction_px": distances[0] - min(distances),
    }


def damage_summary(round_row: dict) -> dict:
    transitions = round_row.get("transitions") or []
    terminal = round_row.get("remaining_hps") or [None, None]
    if not transitions or len(terminal) != 2:
        return {"p1_damage_dealt_hp": 0.0, "p2_damage_dealt_hp": 0.0}
    p1_dealt = 0.0
    p2_dealt = 0.0
    for i, t in enumerate(transitions):
        display = t.get("display") or {}
        p1, p2 = display.get("p1") or {}, display.get("p2") or {}
        try:
            hp1 = float(p1["hp"])
            hp2 = float(p2["hp"])
            if i + 1 < len(transitions):
                nd = transitions[i + 1].get("display") or {}
                nhp1 = float((nd.get("p1") or {})["hp"])
                nhp2 = float((nd.get("p2") or {})["hp"])
            else:
                nhp1 = float(terminal[0])
                nhp2 = float(terminal[1])
        except (KeyError, TypeError, ValueError):
            continue
        p1_dealt += max(0.0, hp2 - nhp2)
        p2_dealt += max(0.0, hp1 - nhp1)
    return {"p1_damage_dealt_hp": p1_dealt, "p2_damage_dealt_hp": p2_dealt}


def discover(root: Path, source_run_url: str | None, recorded_at: str) -> list[dict]:
    rows: list[dict] = []
    for status_path in sorted(root.rglob("status.json")):
        run_dir = status_path.parent
        p1_path, p2_path = run_dir / "p1.jsonl", run_dir / "p2.jsonl"
        if not p1_path.is_file() or not p2_path.is_file():
            continue
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("canonical") is not True:
            continue
        chars = [str(x) for x in (status.get("characters") or [])]
        seeds = [int(x) for x in (status.get("seeds") or [])]
        if len(chars) != 2 or len(seeds) != 2:
            continue
        p1_rounds, p2_rounds = read_jsonl(p1_path), read_jsonl(p2_path)
        if not p1_rounds or len(p1_rounds) != len(p2_rounds):
            continue
        run_id = str(status.get("run_id", run_dir.name))
        for idx, (r1, r2) in enumerate(zip(p1_rounds, p2_rounds), start=1):
            hps = r1.get("remaining_hps") or [None, None]
            if len(hps) != 2:
                continue
            reward = float(r1.get("outcome_reward", 0.0))
            winner = chars[0] if reward > 0 else chars[1] if reward < 0 else "DRAW"
            geometry = round_geometry(r1)
            damage = damage_summary(r1)
            rows.append({
                "match_id": f"{run_id}:r{idx}",
                "recorded_at": recorded_at,
                "source_run_url": source_run_url,
                "run_id": run_id,
                "round": idx,
                "winner": winner,
                "draw": winner == "DRAW",
                "p1": {
                    "character": chars[0], "seed": seeds[0], "final_hp": int(hps[0]),
                    "reward": reward, "decisions": len(r1.get("transitions") or []),
                    "damage_dealt_hp": damage["p1_damage_dealt_hp"],
                    "action_counts": action_counts(r1),
                },
                "p2": {
                    "character": chars[1], "seed": seeds[1], "final_hp": int(hps[1]),
                    "reward": -reward, "decisions": len(r2.get("transitions") or []),
                    "damage_dealt_hp": damage["p2_damage_dealt_hp"],
                    "action_counts": action_counts(r2),
                },
                "hp_margin_p1": int(hps[0]) - int(hps[1]),
                **geometry,
            })
    return rows


def aggregate(matches: list[dict]) -> dict:
    stats = collections.defaultdict(lambda: {"rounds": 0, "wins": 0, "losses": 0, "draws": 0})
    for match in matches:
        for side in ("p1", "p2"):
            ch = match[side]["character"]
            stats[ch]["rounds"] += 1
            reward = float(match[side]["reward"])
            if reward > 0:
                stats[ch]["wins"] += 1
            elif reward < 0:
                stats[ch]["losses"] += 1
            else:
                stats[ch]["draws"] += 1
    return {
        ch: {
            **v,
            "win_rate": (v["wins"] / v["rounds"] if v["rounds"] else 0.0),
            "decisive_win_rate": (v["wins"] / (v["wins"] + v["losses"]) if (v["wins"] + v["losses"]) else None),
        }
        for ch, v in sorted(stats.items())
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifacts-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--source-run-url")
    p.add_argument("--updated-at")
    p.add_argument("--limit", type=int, default=500)
    args = p.parse_args()
    if args.limit < 1:
        p.error("--limit must be positive")

    updated_at = args.updated_at or datetime.now(timezone.utc).isoformat()
    current = discover(args.artifacts_root, args.source_run_url, updated_at)
    if not current:
        raise SystemExit("No canonical rounds found")

    previous: list[dict] = []
    if args.out.is_file():
        try:
            previous = list(json.loads(args.out.read_text(encoding="utf-8")).get("matches") or [])
        except Exception:
            previous = []

    merged: dict[str, dict] = {str(m.get("match_id")): m for m in previous if m.get("match_id")}
    for m in current:
        merged[m["match_id"]] = m
    matches = sorted(merged.values(), key=lambda m: (m.get("recorded_at", ""), m.get("match_id", "")))[-args.limit:]

    payload = {
        "schema_version": 1,
        "kind": "normalized-fightingice-match-log",
        "updated_at": updated_at,
        "canonical_model": "MaleCNS v1.0 + pinned Shiu LIF",
        "raw_neural_log_location": "GitHub Actions artifacts",
        "public_log_policy": "match summaries only; raw spike and membrane data are excluded",
        "match_count": len(matches),
        "character_stats": aggregate(matches),
        "matches": matches,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "match_count": len(matches), "new_matches": len(current), "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
