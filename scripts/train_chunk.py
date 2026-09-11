"""Run one bounded four-character training chunk and export one evaluation replay.

Each FightingICE character owns an independent checkpoint lineage. The immutable
connectome topology may be reused as read-only data, but trainable readout/value
parameters and recurrent state are never shared between characters.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectome_fighter.characters import CHARACTERS, CHARACTER_SEEDS, validate_character
from connectome_fighter.checkpoint import checkpoint_filename, load_checkpoint, save_checkpoint
from connectome_fighter.game_runtime import now_utc, write_json
from connectome_fighter.graph import load_graph
from connectome_fighter.learning import PPOConfig, initialize_heads, make_optimizer, ppo_update
from connectome_fighter.replay import completed_rounds, export_replay
from connectome_fighter.routing import validate_routing


def _elo(r1: float, r2: float, score1: float, k: float = 24.0) -> tuple[float, float]:
    e1 = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
    e2 = 1.0 - e1
    score2 = 1.0 - score1
    return r1 + k * (score1 - e1), r2 + k * (score2 - e2)


def _training_pairs(characters: list[str], chunk: int) -> list[tuple[str, str]]:
    """Return a bounded round-robin slice.

    With the canonical four characters, two disjoint matches per chunk ensure
    every brain trains exactly once; three chunks cover all six pairings.
    """
    if len(characters) == 4:
        a, b, c, d = characters
        schedule = [
            [(a, b), (c, d)],
            [(a, c), (b, d)],
            [(a, d), (b, c)],
        ]
        return schedule[(chunk - 1) % len(schedule)]
    return list(itertools.combinations(characters, 2))


def _load_or_initialize_state(
    state_dir: Path,
    character: str,
    input_dim: int,
    graph_hash: str,
    routing_hash: str,
    code_sha: str,
    config: PPOConfig,
):
    heads = initialize_heads(input_dim, CHARACTER_SEEDS[character])
    optimizer = make_optimizer(heads, config)
    path = state_dir / checkpoint_filename(character)
    if path.is_file():
        payload = load_checkpoint(
            path,
            expected_character=character,
            expected_graph_hash=graph_hash,
            expected_routing_hash=routing_hash,
        )
        heads.actor.load_state_dict(payload["actor_state"])
        heads.critic.load_state_dict(payload["critic_state"])
        optimizer.load_state_dict(payload["optimizer_state"])
        meta = dict(payload["metadata"])
    else:
        meta = save_checkpoint(
            path,
            character=character,
            actor=heads.actor,
            critic=heads.critic,
            optimizer=optimizer,
            generation=0,
            training_matches=0,
            updates=0,
            graph_hash=graph_hash,
            routing_hash=routing_hash,
            code_sha=code_sha,
            hyperparameters=config.as_dict(),
        )
    return heads, optimizer, meta


def _run_match(
    *, host: str, port: int, graph_dir: Path, routing_path: Path, state_dir: Path,
    out_root: Path, run_id: str, p1: str, p2: str, seed1: int, seed2: int,
    evaluation: bool, timeout: float, neural_steps: int,
) -> Path:
    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_game.py"),
        "--host", host, "--port", str(port), "--games", "1",
        "--policy", "connectome",
        "--graph-dir", str(graph_dir), "--routing", str(routing_path),
        "--character-p1", p1, "--character-p2", p2,
        "--checkpoint-p1", str(state_dir / checkpoint_filename(p1)),
        "--checkpoint-p2", str(state_dir / checkpoint_filename(p2)),
        "--seed-p1", str(seed1), "--seed-p2", str(seed2),
        "--timeout", str(timeout), "--expected-rounds", "1",
        "--neural-steps", str(neural_steps), "--torch-threads", "1",
        "--run-id", run_id, "--out", str(out_root),
    ]
    if evaluation:
        cmd.append("--evaluation")
    subprocess.run(cmd, cwd=ROOT, check=True)
    return out_root / run_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=31415)
    parser.add_argument("--graph-dir", type=Path, required=True)
    parser.add_argument("--routing", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    parser.add_argument("--out", type=Path, default=Path("runs/continuous"))
    parser.add_argument("--characters", nargs="+", default=list(CHARACTERS))
    parser.add_argument("--train-games-per-pair", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--neural-steps", type=int, default=1)
    parser.add_argument("--code-sha", default=os.environ.get("GITHUB_SHA", "unknown"))
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--ppo-epochs", type=int, default=4)
    args = parser.parse_args()
    characters = [validate_character(x) for x in args.characters]
    if len(characters) != len(set(characters)) or len(characters) < 2:
        parser.error("Need at least two unique characters")
    if args.train_games_per_pair <= 0 or args.timeout <= 0 or args.neural_steps <= 0:
        parser.error("Training games, timeout and neural steps must be positive")

    args.state_dir.mkdir(parents=True, exist_ok=True)
    live_root = args.out / "live"
    site_data = args.out / "site-data"
    live_root.mkdir(parents=True, exist_ok=True)
    site_data.mkdir(parents=True, exist_ok=True)

    routing = json.loads(args.routing.read_text(encoding="utf-8"))
    graph = load_graph(args.graph_dir, require_biological=True)
    validate_routing(graph, routing)
    graph_hash = graph.fingerprint()
    routing_hash = routing["routing_sha256"]
    input_dim = len(routing["output_nodes"])
    # Release the large graph arrays in this coordinator. Each live-match child
    # process loads the graph and exits, bounding peak memory per match.
    del graph

    config = PPOConfig(learning_rate=args.learning_rate, epochs=args.ppo_epochs)
    heads: dict[str, Any] = {}
    optimizers: dict[str, Any] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for character in characters:
        h, o, m = _load_or_initialize_state(
            args.state_dir, character, input_dim, graph_hash, routing_hash, args.code_sha, config
        )
        heads[character], optimizers[character], metadata[character] = h, o, m

    league_path = args.state_dir / "league-state.json"
    if league_path.is_file():
        league = json.loads(league_path.read_text(encoding="utf-8"))
    else:
        league = {
            "schema_version": 1,
            "chunks": 0,
            "elo": {c: 1500.0 for c in characters},
            "history": {c: [] for c in characters},
        }
    for c in characters:
        league.setdefault("elo", {}).setdefault(c, 1500.0)
        league.setdefault("history", {}).setdefault(c, [])

    chunk = int(league.get("chunks", 0)) + 1
    rounds_by_character: dict[str, list[dict[str, Any]]] = {c: [] for c in characters}
    all_pairs = list(itertools.combinations(characters, 2))
    train_pairs = _training_pairs(characters, chunk)
    match_counter = 0
    for repeat in range(args.train_games_per_pair):
        for p1, p2 in train_pairs:
            match_counter += 1
            run_id = f"tr-c{chunk:05d}-{match_counter:02d}-{p1.lower()}-{p2.lower()}"
            run_dir = _run_match(
                host=args.host, port=args.port, graph_dir=args.graph_dir, routing_path=args.routing,
                state_dir=args.state_dir, out_root=live_root, run_id=run_id,
                p1=p1, p2=p2,
                seed1=CHARACTER_SEEDS[p1] + chunk * 100 + match_counter,
                seed2=CHARACTER_SEEDS[p2] + chunk * 100 + match_counter,
                evaluation=False, timeout=args.timeout, neural_steps=args.neural_steps,
            )
            p1_rounds = completed_rounds(run_dir / "p1.jsonl")
            p2_rounds = completed_rounds(run_dir / "p2.jsonl")
            if len(p1_rounds) != 1 or len(p2_rounds) != 1:
                raise RuntimeError("Training match did not produce exactly one audited round per player")
            if not p1_rounds[0].get("trainable") or not p2_rounds[0].get("trainable"):
                raise RuntimeError("Training match was unexpectedly marked non-trainable")
            rounds_by_character[p1].extend(p1_rounds)
            rounds_by_character[p2].extend(p2_rounds)

    training_metrics: dict[str, Any] = {}
    for character in characters:
        character_rounds = rounds_by_character[character]
        if not character_rounds:
            raise RuntimeError(f"Character {character} received no training match in this chunk")
        metrics = ppo_update(heads[character], optimizers[character], character_rounds, config)
        previous = metadata[character]
        new_meta = save_checkpoint(
            args.state_dir / checkpoint_filename(character),
            character=character,
            actor=heads[character].actor,
            critic=heads[character].critic,
            optimizer=optimizers[character],
            generation=int(previous.get("generation", 0)) + 1,
            training_matches=int(previous.get("training_matches", 0)) + len(character_rounds),
            updates=int(previous.get("updates", 0)) + 1,
            graph_hash=graph_hash,
            routing_hash=routing_hash,
            code_sha=args.code_sha,
            hyperparameters=config.as_dict(),
        )
        metadata[character] = new_meta
        training_metrics[character] = {**metrics, "rounds": len(character_rounds)}

    # Rotate the public evaluation matchup independently of the training slice.
    eval_pair = all_pairs[(chunk - 1) % len(all_pairs)]
    ep1, ep2 = eval_pair
    eval_id = f"eval-c{chunk:05d}-{ep1.lower()}-{ep2.lower()}"
    eval_dir = _run_match(
        host=args.host, port=args.port, graph_dir=args.graph_dir, routing_path=args.routing,
        state_dir=args.state_dir, out_root=live_root, run_id=eval_id,
        p1=ep1, p2=ep2,
        seed1=900_000 + chunk * 2, seed2=900_001 + chunk * 2,
        evaluation=True, timeout=args.timeout, neural_steps=args.neural_steps,
    )
    er1, er2 = completed_rounds(eval_dir / "p1.jsonl"), completed_rounds(eval_dir / "p2.jsonl")
    if len(er1) != 1 or len(er2) != 1:
        raise RuntimeError("Evaluation did not complete")
    if er1[0].get("trainable") or er2[0].get("trainable"):
        raise RuntimeError("Evaluation trace must never be trainable")
    reward = float(er1[0]["outcome_reward"])
    score1 = 1.0 if reward > 0 else 0.0 if reward < 0 else 0.5
    r1, r2 = float(league["elo"][ep1]), float(league["elo"][ep2])
    league["elo"][ep1], league["elo"][ep2] = _elo(r1, r2, score1)
    league["chunks"] = chunk
    league["last_training_pairs"] = [list(x) for x in train_pairs]
    for c in characters:
        league["history"][c].append({
            "chunk": chunk,
            "generation": metadata[c]["generation"],
            "elo": round(float(league["elo"][c]), 3),
            "training_matches": metadata[c]["training_matches"],
        })
        league["history"][c] = league["history"][c][-300:]
    write_json(league_path, league)

    replay_path = site_data / "latest-replay.json"
    replay = export_replay(
        eval_dir / "p1.jsonl", eval_dir / "p2.jsonl", replay_path,
        p1_character=ep1, p2_character=ep2,
    )
    status = {
        "schema_version": 2,
        "phase": "continuous-training",
        "updated_at": now_utc(),
        "chunk": chunk,
        "training_pairs": [list(x) for x in train_pairs],
        "graph_sha256": graph_hash,
        "routing_sha256": routing_hash,
        "characters": {
            c: {
                "character": c,
                "lineage_id": metadata[c]["lineage_id"],
                "checkpoint_id": metadata[c]["checkpoint_id"],
                "generation": metadata[c]["generation"],
                "training_matches": metadata[c]["training_matches"],
                "elo": round(float(league["elo"][c]), 2),
                "history": league["history"][c],
                "last_update": training_metrics[c],
            }
            for c in characters
        },
        "latest_match": {
            "p1": ep1,
            "p2": ep2,
            "winner": replay["result"]["winner"],
            "replay_url": "./data/latest-replay.json",
            "evaluation": True,
        },
    }
    write_json(site_data / "status.json", status)
    write_json(args.out / "chunk-summary.json", {
        "status": "COMPLETED",
        "chunk": chunk,
        "training_pairs": [list(x) for x in train_pairs],
        "characters": metadata,
        "training_metrics": training_metrics,
        "evaluation": status["latest_match"],
        "updated_at": status["updated_at"],
    })
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
