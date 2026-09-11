"""Real-game inference and trace collection. This script never updates weights."""
from __future__ import annotations
import argparse
import asyncio
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from connectome_fighter.game_runtime import now_utc, write_json
from connectome_fighter.characters import CHARACTER_SEEDS, validate_character


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=31415)
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--policy", choices=["random", "connectome"], default="random")
    parser.add_argument("--graph-dir")
    parser.add_argument("--routing")
    parser.add_argument("--character-p1", default="ZEN")
    parser.add_argument("--character-p2", default="ZEN")
    parser.add_argument("--checkpoint-p1")
    parser.add_argument("--checkpoint-p2")
    parser.add_argument("--evaluation", action="store_true",
                        help="Mark emitted rounds non-trainable; weights are never updated here")
    parser.add_argument("--activity-top-k", type=int, default=12)
    parser.add_argument("--out", type=Path, default=Path("runs/live"))
    parser.add_argument("--timeout", type=float, default=300.)
    parser.add_argument("--run-id")
    parser.add_argument("--seed-p1", type=int, default=10)
    parser.add_argument("--seed-p2", type=int, default=20)
    parser.add_argument("--expected-rounds", type=int)
    parser.add_argument("--neural-steps", type=int, default=1,
                        help="Engineering recurrent updates per game decision; not biological milliseconds")
    parser.add_argument("--torch-threads", type=int, default=1)
    args = parser.parse_args()
    args.character_p1 = validate_character(args.character_p1)
    args.character_p2 = validate_character(args.character_p2)
    if (args.games <= 0 or args.timeout <= 0 or not 1 <= args.port <= 65535
        or args.neural_steps <= 0 or args.torch_threads <= 0 or args.activity_top_k <= 0):
        parser.error("Invalid count, timeout, port, neural step count, thread count, or activity top-k")
    if args.expected_rounds is not None and args.expected_rounds <= 0:
        parser.error("Expected rounds must be positive")
    run_id = args.run_id or uuid.uuid4().hex[:12]
    if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", run_id) is None:
        parser.error("Invalid run-id")
    if args.policy == "connectome" and (not args.graph_dir or not args.routing):
        parser.error("Connectome mode requires --graph-dir and --routing")
    out = args.out.resolve()/run_id
    out.mkdir(parents=True, exist_ok=False)
    try:
        pyftg_version = importlib.metadata.version("pyftg")
    except importlib.metadata.PackageNotFoundError:
        pyftg_version = None
    status = {
        "started_at_utc": now_utc(), "status": "STARTING", "learning_performed": False,
        "evaluation": bool(args.evaluation), "connectome_used": args.policy == "connectome",
        "characters": [args.character_p1, args.character_p2],
        "host": args.host, "port": args.port, "games_requested": args.games,
        "seeds": [args.seed_p1, args.seed_p2], "python": sys.version.split()[0],
        "pyftg": pyftg_version,
        "neural_steps_per_decision": (args.neural_steps if args.policy == "connectome" else None),
        "torch_threads": (args.torch_threads if args.policy == "connectome" else None),
    }
    write_json(out/"status.json", status)
    agents = []
    code = 1
    try:
        from pyftg.socket.aio.gateway import Gateway
        from connectome_fighter.pyftg_bridge import FighterAI
        from connectome_fighter.policies import RandomPolicy
        from connectome_fighter.trajectory import JsonlSink
        seeds = [args.seed_p1, args.seed_p2]
        characters = [args.character_p1, args.character_p2]
        if args.policy == "random":
            policies = [RandomPolicy(seed, f"random-{characters[i]}-{seed}") for i, seed in enumerate(seeds)]
        else:
            import numpy as np
            import torch
            from connectome_fighter.graph import load_graph
            from connectome_fighter.brain import ConnectomeActorCritic, NeuralPolicy, SparseGraphCore
            from connectome_fighter.checkpoint import load_checkpoint
            from connectome_fighter.routing import validate_routing
            torch.set_num_threads(args.torch_threads)
            graph_dir = Path(args.graph_dir)
            graph = load_graph(graph_dir, require_biological=True)
            routing = json.loads(Path(args.routing).read_text())
            validate_routing(graph, routing)
            graph_hash = graph.fingerprint()
            routing_hash = routing["routing_sha256"]
            status["graph_sha256"] = graph_hash
            status["routing_sha256"] = routing_hash
            status["routing_annotation_version"] = routing.get("annotation_version")
            status["input_neurons"] = len(routing["input_nodes"])
            status["output_neurons"] = len(routing["output_nodes"])

            node_positions = None
            brain_bounds = None
            coordinate_space = None
            metadata_path = graph_dir / "node_metadata.npz"
            if metadata_path.is_file():
                with np.load(metadata_path, allow_pickle=False) as data:
                    positions = np.asarray(data["positions"], dtype=np.float32)
                    bounds_min = np.asarray(data["bounds_min"], dtype=np.float32)
                    bounds_max = np.asarray(data["bounds_max"], dtype=np.float32)
                    raw_space = np.asarray(data["coordinate_space"]).reshape(-1)
                    if positions.shape != (graph.n_nodes, 3):
                        raise ValueError("node_metadata.npz is not aligned to the graph")
                    node_positions = positions.copy()
                    brain_bounds = (bounds_min.copy(), bounds_max.copy())
                    coordinate_space = str(raw_space[0]) if raw_space.size else "FlyWire annotation coordinates"
                status["node_metadata"] = {
                    "path": str(metadata_path),
                    "positioned_nodes": int(np.isfinite(node_positions).all(axis=1).sum()),
                    "coordinate_space": coordinate_space,
                }
            else:
                status["node_metadata"] = None

            # The immutable anatomical matrix is shared only as a memory
            # optimization. Each character has a distinct recurrent state,
            # actor/critic parameters, RNG and checkpoint lineage.
            shared_core = SparseGraphCore(graph, plastic=False)
            policies = []
            checkpoint_paths = [args.checkpoint_p1, args.checkpoint_p2]
            checkpoint_meta = []
            for i, (seed, character, checkpoint_path) in enumerate(zip(seeds, characters, checkpoint_paths)):
                torch.manual_seed(CHARACTER_SEEDS[character])
                model = ConnectomeActorCritic(
                    graph,
                    routing["input_nodes"], routing["output_nodes"],
                    input_features=routing["input_features"],
                    input_polarities=routing["input_polarities"],
                    input_scale=float(routing["selection"]["input_scale"]),
                    neural_steps=args.neural_steps,
                    plastic=False,
                    shared_core=shared_core,
                )
                if checkpoint_path:
                    payload = load_checkpoint(
                        checkpoint_path,
                        expected_character=character,
                        expected_graph_hash=graph_hash,
                        expected_routing_hash=routing_hash,
                    )
                    model.actor.load_state_dict(payload["actor_state"])
                    model.critic.load_state_dict(payload["critic_state"])
                    meta = payload["metadata"]
                    version = meta["checkpoint_id"]
                    checkpoint_meta.append(meta)
                else:
                    version = f"untrained-{character.lower()}-{graph_hash[:10]}-{routing_hash[:8]}"
                    checkpoint_meta.append({"character": character, "checkpoint_id": version, "generation": 0})
                policies.append(NeuralPolicy(
                    model, version, seed,
                    node_ids=graph.node_ids,
                    node_positions=node_positions,
                    brain_bounds=brain_bounds,
                    coordinate_space=coordinate_space,
                    activity_top_k=args.activity_top_k,
                ))
            status["checkpoints"] = checkpoint_meta
            status["immutable_core_shared_between_agents"] = True

        # FightingICE keeps AI registrations for the lifetime of the Java
        # process. Reusing the same registration names in a later match can
        # leave a new client bound to stale registrations. Include the run_id so
        # every match, including evaluation rematches, registers fresh AI names.
        agents = [
            FighterAI(
                f"ConnectomeFighter-{characters[i]}-P{i+1}-{run_id}",
                policy,
                JsonlSink(out/f"p{i+1}.jsonl"),
                run_id,
                policies[1-i].version,
                trainable=not args.evaluation,
            )
            for i, policy in enumerate(policies)
        ]

        async def run() -> None:
            gateway = Gateway(host=args.host, port=args.port)
            for ai in agents:
                gateway.register_ai(ai.name(), ai)
            try:
                await asyncio.wait_for(
                    gateway.run_game(characters, [a.name() for a in agents], args.games),
                    timeout=args.timeout)
            finally:
                for ai in agents:
                    ai.close()
                await asyncio.wait_for(gateway.close(), timeout=5)

        asyncio.run(run())
        from connectome_fighter.match_audit import audit_pair
        audit = audit_pair(out/"p1.jsonl", out/"p2.jsonl", args.expected_rounds)
        status["audit"] = audit
        status["status"] = "COMPLETED_WITH_VALIDATED_TRACES"
        code = 0
    except KeyboardInterrupt:
        status["status"], status["error"] = "INTERRUPTED", "Interrupted by user"
        code = 130
    except Exception as exc:
        trace = traceback.format_exc()
        (out/"exception_traceback.txt").write_text(trace, encoding="utf-8")
        status["status"], status["error"] = "FAILED", f"{type(exc).__name__}: {exc}"
        status["traceback_file"] = "exception_traceback.txt"
        print(trace, file=sys.stderr)
    finally:
        for ai in agents:
            ai.close()
        status["completed_rounds_per_agent"] = [ai.ledger.completed for ai in agents]
        status["finished_at_utc"] = now_utc()
        status["exit_code"] = code
        write_json(out/"status.json", status)
        print(json.dumps({"status": status["status"], "path": str(out),
                          "completed_rounds_per_agent": status["completed_rounds_per_agent"],
                          "error": status.get("error"), "learning_performed": False}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
