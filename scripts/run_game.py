"""Real-game inference and trace collection. This script does not train a policy."""
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=31415)
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--policy", choices=["random", "connectome"], default="random")
    parser.add_argument("--graph-dir")
    parser.add_argument("--routing")
    parser.add_argument("--out", type=Path, default=Path("runs/live"))
    parser.add_argument("--timeout", type=float, default=300.)
    parser.add_argument("--run-id")
    parser.add_argument("--seed-p1", type=int, default=10)
    parser.add_argument("--seed-p2", type=int, default=20)
    parser.add_argument("--expected-rounds", type=int)
    args = parser.parse_args()
    if args.games <= 0 or args.timeout <= 0 or not 1 <= args.port <= 65535:
        parser.error("Invalid count, timeout, or port")
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
    status = {"started_at_utc": now_utc(), "status": "STARTING", "learning_performed": False,
              "connectome_used": args.policy == "connectome", "host": args.host, "port": args.port,
              "games_requested": args.games, "seeds": [args.seed_p1, args.seed_p2],
              "python": sys.version.split()[0], "pyftg": pyftg_version}
    write_json(out/"status.json", status)
    agents = []
    code = 1
    try:
        from pyftg.socket.aio.gateway import Gateway
        from connectome_fighter.pyftg_bridge import FighterAI
        from connectome_fighter.policies import RandomPolicy
        from connectome_fighter.trajectory import JsonlSink
        seeds = [args.seed_p1, args.seed_p2]
        if args.policy == "random":
            policies = [RandomPolicy(seed) for seed in seeds]
        else:
            import torch
            from connectome_fighter.graph import load_graph
            from connectome_fighter.brain import ConnectomeActorCritic, NeuralPolicy
            torch.set_num_threads(1)
            graph = load_graph(args.graph_dir, require_biological=True)
            routing = json.loads(Path(args.routing).read_text())
            policies = []
            for seed in seeds:
                torch.manual_seed(seed)
                model = ConnectomeActorCritic(graph, routing["input_nodes"], routing["output_nodes"])
                policies.append(NeuralPolicy(model, f"untrained-{graph.fingerprint()[:12]}-{seed}", seed))
        agents = [FighterAI(f"ConnectomeFighterP{i+1}", policy, JsonlSink(out/f"p{i+1}.jsonl"),
                            run_id, policies[1-i].version) for i, policy in enumerate(policies)]

        async def run() -> None:
            gateway = Gateway(host=args.host, port=args.port)
            for ai in agents:
                gateway.register_ai(ai.name(), ai)
            try:
                await asyncio.wait_for(
                    gateway.run_game(["ZEN", "ZEN"], [a.name() for a in agents], args.games),
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
