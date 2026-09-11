"""Run one FightingICE match with two independent MaleCNS+Shiu LIF brains.

There is no learned artificial neural network in this control path. Each
character owns a separate Brian2 worker process with independent membrane/
synaptic state and RNG. Per-character adapter directories may contain only
magnitude changes on the approved existing KC->MBON rows; pinned Shiu dynamics
remain unchanged.
"""
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
sys.path.insert(0, str(ROOT / "src"))

from connectome_fighter.characters import validate_character
from connectome_fighter.game_runtime import now_utc, write_json


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=31415)
    p.add_argument("--character-p1", default="GARNET")
    p.add_argument("--character-p2", default="ZEN")
    p.add_argument("--seed-p1", type=int, default=10101)
    p.add_argument("--seed-p2", type=int, default=20202)
    p.add_argument("--reference-python", required=True,
                   help="Python executable containing pinned Brian2/Shiu runtime dependencies")
    p.add_argument("--reference-model", type=Path, required=True)
    p.add_argument("--worker-script", type=Path, default=ROOT / "scripts" / "malecns_lif_worker.py")
    p.add_argument("--adapter-dir", type=Path, required=True,
                   help="Default adapter used for both sides unless side-specific adapter is supplied")
    p.add_argument("--adapter-dir-p1", type=Path)
    p.add_argument("--adapter-dir-p2", type=Path)
    p.add_argument("--interface", type=Path, required=True)
    p.add_argument("--decision-interval", type=int, default=30,
                   help="FightingICE frames between expensive canonical LIF decisions")
    p.add_argument("--games", type=int, default=1)
    p.add_argument("--expected-rounds", type=int, default=1)
    p.add_argument("--timeout", type=float, default=900.0)
    p.add_argument("--trainable-trace", action="store_true",
                   help="Mark round traces eligible for post-match reward plasticity; no weights change during play")
    p.add_argument("--run-id")
    p.add_argument("--out", type=Path, default=Path("runs/malecns-live"))
    args = p.parse_args()

    args.character_p1 = validate_character(args.character_p1)
    args.character_p2 = validate_character(args.character_p2)
    adapter_dirs = [args.adapter_dir_p1 or args.adapter_dir, args.adapter_dir_p2 or args.adapter_dir]
    if args.games <= 0 or args.expected_rounds <= 0 or args.timeout <= 0:
        p.error("games/rounds/timeout must be positive")
    if args.decision_interval <= 0 or not 1 <= args.port <= 65535:
        p.error("invalid decision interval or port")
    run_id = args.run_id or ("malecns-" + uuid.uuid4().hex[:10])
    if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", run_id) is None:
        p.error("invalid run-id")
    for required in [args.reference_model, args.worker_script, args.interface]:
        if not required.exists():
            p.error(f"missing required canonical input: {required}")
    for adapter in adapter_dirs:
        for filename in ["manifest.json", "completeness.csv", "connectivity.parquet"]:
            required = adapter / filename
            if not required.exists():
                p.error(f"missing required per-character adapter input: {required}")

    out = (args.out / run_id).resolve()
    out.mkdir(parents=True, exist_ok=False)
    status = {
        "status": "STARTING",
        "started_at_utc": now_utc(),
        "run_id": run_id,
        "canonical": True,
        "learning_performed": False,
        "trace_trainable": bool(args.trainable_trace),
        "brain_model": "MaleCNS v1.0 + pinned Shiu LIF",
        "characters": [args.character_p1, args.character_p2],
        "seeds": [args.seed_p1, args.seed_p2],
        "decision_interval_frames": args.decision_interval,
        "games_requested": args.games,
        "host": args.host,
        "port": args.port,
    }
    write_json(out / "status.json", status)
    policies = []
    agents = []
    code = 1

    try:
        from pyftg.socket.aio.gateway import Gateway
        from connectome_fighter.malecns_worker_policy import MaleCNSWorkerPolicy
        from connectome_fighter.pyftg_bridge import FighterAI
        from connectome_fighter.trajectory import JsonlSink

        try:
            status["pyftg"] = importlib.metadata.version("pyftg")
        except importlib.metadata.PackageNotFoundError:
            status["pyftg"] = None

        interface = json.loads(args.interface.read_text(encoding="utf-8"))
        interface_hash = interface["interface_sha256"]
        characters = [args.character_p1, args.character_p2]
        seeds = [args.seed_p1, args.seed_p2]
        status["character_adapters"] = []
        for i, (character, seed, adapter_dir) in enumerate(
            zip(characters, seeds, adapter_dirs), start=1
        ):
            adapter_manifest = json.loads((adapter_dir / "manifest.json").read_text(encoding="utf-8"))
            plasticity = adapter_manifest.get("plasticity") or {}
            generation = int(plasticity.get("generation", 0))
            version = (
                f"malecns-shiu-{character.lower()}-g{generation:06d}-"
                f"{interface_hash[:10]}-seed{seed}"
            )
            policy = MaleCNSWorkerPolicy(
                character=character,
                seed=seed,
                version=version,
                python_executable=args.reference_python,
                worker_script=args.worker_script,
                reference_model=args.reference_model,
                adapter_dir=adapter_dir,
                interface_path=args.interface,
                trace_root=out / f"p{i}-brain",
                run_id=f"{run_id}-p{i}",
            )
            policies.append(policy)
            status["character_adapters"].append({
                "character": character,
                "adapter": adapter_manifest.get("adapter"),
                "plasticity": plasticity,
            })
        status["workers"] = [p.worker_ready for p in policies]
        status["interface_sha256"] = interface_hash
        write_json(out / "status.json", status)

        agents = [
            FighterAI(
                f"CF-{run_id}-P{i+1}-{characters[i]}",
                policies[i],
                JsonlSink(out / f"p{i+1}.jsonl"),
                run_id,
                policies[1-i].version,
                decision_interval=args.decision_interval,
                trainable=bool(args.trainable_trace),
            )
            for i in range(2)
        ]

        async def run() -> None:
            gateway = Gateway(host=args.host, port=args.port)
            for ai in agents:
                gateway.register_ai(ai.name(), ai)
            try:
                await asyncio.wait_for(
                    gateway.run_game(characters, [a.name() for a in agents], args.games),
                    timeout=args.timeout,
                )
            finally:
                for ai in agents:
                    ai.close()
                await asyncio.wait_for(gateway.close(), timeout=5)

        asyncio.run(run())
        from connectome_fighter.match_audit import audit_pair
        audit = audit_pair(
            out / "p1.jsonl", out / "p2.jsonl", args.expected_rounds,
            expected_trainable=bool(args.trainable_trace),
        )
        status["audit"] = audit
        status["status"] = "COMPLETED_WITH_VALIDATED_CANONICAL_TRACES"
        code = 0
    except KeyboardInterrupt:
        status["status"] = "INTERRUPTED"
        status["error"] = "Interrupted by user"
        code = 130
    except Exception as exc:
        trace = traceback.format_exc()
        (out / "exception_traceback.txt").write_text(trace, encoding="utf-8")
        status["status"] = "FAILED"
        status["error"] = f"{type(exc).__name__}: {exc}"
        status["traceback_file"] = "exception_traceback.txt"
        print(trace, file=sys.stderr)
    finally:
        for ai in agents:
            try:
                ai.close()
            except Exception:
                pass
        for policy in policies:
            try:
                policy.close()
            except Exception:
                pass
        status["completed_rounds_per_agent"] = [a.ledger.completed for a in agents]
        status["finished_at_utc"] = now_utc()
        status["exit_code"] = code
        write_json(out / "status.json", status)
        print(json.dumps({
            "status": status["status"],
            "path": str(out),
            "completed_rounds_per_agent": status["completed_rounds_per_agent"],
            "error": status.get("error"),
        }, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
