#!/usr/bin/env python3
"""Run one read-only FightingICE + MaleCNS session and expose live telemetry.

The HTTP/SSE server is a spectator side channel. It never supplies data to the
policies, never changes weights, and never reads screen pixels for control.
"""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Any


def rounds_per_session_from_env() -> int:
    """Use proven multi-round reuse for the shared broadcast, one round elsewhere."""
    public = os.environ.get("CONNECTOME_PUBLIC_BROADCAST", "false").strip().lower() == "true"
    default = "6" if public else "1"
    raw = os.environ.get("CONNECTOME_ROUNDS_PER_SESSION", default).strip()
    try:
        rounds = int(raw)
    except ValueError as exc:
        raise ValueError(f"CONNECTOME_ROUNDS_PER_SESSION must be an integer, got {raw!r}") from exc
    if not 1 <= rounds <= 60:
        raise ValueError(f"CONNECTOME_ROUNDS_PER_SESSION must be in [1, 60], got {rounds}")
    return rounds


class ArenaState:
    def __init__(self, *, session_id: str, p1: str, p2: str, max_hp: int, rounds_per_session: int = 1) -> None:
        self.session_id = session_id
        self.characters = {1: p1, 2: p2}
        self.max_hp = int(max_hp)
        self.rounds_per_session = int(rounds_per_session)
        self.lock = threading.Condition()
        self.latest: dict[int, dict[str, Any]] = {}
        self.sequence = 0
        self.process_status = "booting"
        self.error: str | None = None
        self.exit_code: int | None = None

    def update(self, event: dict[str, Any]) -> None:
        side = int(event.get("side", 0))
        if side not in (1, 2):
            return
        with self.lock:
            self.latest[side] = event
            self.process_status = "running"
            self.sequence += 1
            self.lock.notify_all()

    def finish(self, returncode: int, error: str | None = None) -> None:
        with self.lock:
            self.exit_code = int(returncode)
            self.error = error
            self.process_status = "ended" if returncode == 0 and not error else "error"
            self.sequence += 1
            self.lock.notify_all()

    @staticmethod
    def _brain_sample(event: dict[str, Any] | None) -> dict[str, Any]:
        event = event or {}
        brain = event.get("brain") or {}
        top = brain.get("top_spike_bodies") or []
        top_bodies = []
        for row in top[:20]:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            top_bodies.append({"body_id": int(row[0]), "spikes": int(row[1])})

        raw_groups = brain.get("group_spike_counts") or {}
        group_spike_counts = {
            str(name): int(value)
            for name, value in raw_groups.items()
            if isinstance(name, str) and isinstance(value, (int, float))
        }

        sensory_drive = []
        for row in (brain.get("sensory_drive_top") or [])[:16]:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            try:
                sensory_drive.append({"body_id": int(row[0]), "rate_hz": float(row[1])})
            except (TypeError, ValueError):
                continue

        output_contributions = []
        for row in (brain.get("output_contributions_top") or [])[:20]:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            try:
                output_contributions.append({
                    "group": str(row[0]),
                    "body_id": int(row[1]),
                    "spikes": float(row[2]),
                })
            except (TypeError, ValueError):
                continue

        membrane_summary = {}
        for name, value in (brain.get("membrane_summary") or {}).items():
            if isinstance(name, str) and isinstance(value, (int, float)):
                membrane_summary[name] = float(value)

        return {
            "decision_index": int(brain.get("trace_decision_index", 0)),
            "t_seconds": float(event.get("frame", 0)) / 60.0,
            "biological_time_start_ms": float(brain.get("biological_time_start_ms", 0.0)),
            "biological_time_end_ms": float(brain.get("biological_time_end_ms", 0.0)),
            "total_spikes": int(brain.get("total_spikes", 0)),
            "unique_bodies": int(brain.get("unique_spike_bodies", len(top_bodies))),
            "group_spike_counts": group_spike_counts,
            "sensory_drive": sensory_drive,
            "output_contributions": output_contributions,
            "membrane_summary": membrane_summary,
            "neuromeres": [],
            "superclasses": [],
            "types": [],
            "top_bodies": top_bodies,
        }

    def payload(self) -> dict[str, Any]:
        with self.lock:
            e1 = self.latest.get(1)
            e2 = self.latest.get(2)
            status = self.process_status
            error = self.error
            exit_code = self.exit_code

        display = ((e1 or e2 or {}).get("display") or {})
        p1_display = display.get("p1") or {}
        p2_display = display.get("p2") or {}
        frame = int(display.get("frame", max(int((e1 or {}).get("frame", 0)), int((e2 or {}).get("frame", 0)))))
        round_id = int(max(int((e1 or {}).get("round_id", 0)), int((e2 or {}).get("round_id", 0))))

        def fighter(side: int, event: dict[str, Any] | None, row: dict[str, Any]) -> dict[str, Any]:
            return {
                "character": self.characters[side],
                "hp": int(row.get("hp", self.max_hp)),
                "max_hp": self.max_hp,
                "x": float(row.get("x", 0)),
                "y": float(row.get("y", 0)),
                "action": str((event or {}).get("action_name", "NEUTRAL")),
                "facing": "right" if bool((event or {}).get("facing_right", True)) else "left",
                "energy": int(row.get("energy", 0)),
            }

        return {
            "schema_version": 3,
            "session_id": self.session_id,
            "status": status,
            "round": round_id,
            "rounds_per_session": self.rounds_per_session,
            "frame": frame,
            "t_seconds": frame / 60.0,
            "p1": fighter(1, e1, p1_display),
            "p2": fighter(2, e2, p2_display),
            "brain": {
                "p1": self._brain_sample(e1),
                "p2": self._brain_sample(e2),
            },
            "learning_enabled": False,
            "policy_pixel_access": False,
            "error": error,
            "exit_code": exit_code,
        }


def tail_jsonl(path: Path, state: ArenaState, stop: threading.Event) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    partial = ""
    while not stop.is_set():
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    handle.seek(offset)
                    chunk = handle.read()
                    offset = handle.tell()
                if chunk:
                    partial += chunk
                    lines = partial.split("\n")
                    partial = lines.pop()
                    for line in lines:
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if event.get("kind") == "decision":
                            state.update(event)
        except OSError:
            pass
        stop.wait(0.08)


def make_handler(state: ArenaState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ConnectomeArena/3"

        def _headers(self, status: int, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

        def log_message(self, fmt: str, *args) -> None:
            return

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._headers(HTTPStatus.OK, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": True, "status": state.process_status}).encode())
                return
            if path == "/state":
                self._headers(HTTPStatus.OK, "application/json; charset=utf-8")
                self.wfile.write(json.dumps(state.payload(), separators=(",", ":"), allow_nan=False).encode())
                return
            if path == "/events":
                self._headers(HTTPStatus.OK, "text/event-stream; charset=utf-8")
                last = -1
                try:
                    while True:
                        with state.lock:
                            if state.sequence == last:
                                state.lock.wait(timeout=10.0)
                            last = state.sequence
                            payload = state.payload()
                        data = json.dumps(payload, separators=(",", ":"), allow_nan=False)
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                        if payload["status"] in {"ended", "error"}:
                            return
                except (BrokenPipeError, ConnectionResetError):
                    return
            self._headers(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8")
            self.wfile.write(b'{"error":"not_found"}')

    return Handler


def log_tail(path: Path, max_chars: int = 2400) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-max_chars:]


def wait_for_fightingice(log_path: Path, proc: subprocess.Popen, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = log_tail(log_path)
            suffix = f"; log_tail={tail}" if tail else ""
            raise RuntimeError(f"FightingICE exited before socket startup (rc={proc.returncode}){suffix}")
        if log_path.exists() and "Socket server is started" in log_path.read_text(encoding="utf-8", errors="replace"):
            return
        time.sleep(0.5)
    raise TimeoutError("FightingICE socket did not start before timeout")


def hold_observable(seconds: float, stopping: callable) -> None:
    """Keep terminal/error state queryable long enough for external health checks."""
    deadline = time.time() + max(0.0, float(seconds))
    while time.time() < deadline and not stopping():
        time.sleep(0.2)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--listen", type=int, default=8080)
    p.add_argument("--session-id", required=True)
    p.add_argument("--p1", required=True)
    p.add_argument("--p2", required=True)
    p.add_argument("--seed-p1", type=int, default=800101)
    p.add_argument("--seed-p2", type=int, default=800202)
    p.add_argument("--max-hp", type=int, default=400)
    p.add_argument("--decision-interval", type=int, default=60)
    p.add_argument("--game-port", type=int, default=31415)
    p.add_argument("--game-jar", type=Path, required=True)
    p.add_argument("--reference-python", required=True)
    p.add_argument("--reference-model", type=Path, required=True)
    p.add_argument("--adapter-dir", type=Path, required=True)
    p.add_argument("--adapter-dir-p1", type=Path)
    p.add_argument("--adapter-dir-p2", type=Path)
    p.add_argument("--interface", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("/tmp/connectome-arena"))
    p.add_argument("--post-fight-seconds", type=float, default=30.0)
    p.add_argument("--fightingice-mode", choices=["lightweight", "headless"], default="lightweight")
    args = p.parse_args()
    rounds_per_session = rounds_per_session_from_env()

    args.out.mkdir(parents=True, exist_ok=True)
    telemetry_path = args.out / "live-decisions.jsonl"
    game_log = args.out / "fightingice.log"
    state = ArenaState(
        session_id=args.session_id,
        p1=args.p1,
        p2=args.p2,
        max_hp=args.max_hp,
        rounds_per_session=rounds_per_session,
    )
    stop = threading.Event()
    tailer = threading.Thread(target=tail_jsonl, args=(telemetry_path, state, stop), daemon=True)
    tailer.start()

    server = ThreadingHTTPServer(("0.0.0.0", args.listen), make_handler(state))
    server_thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    server_thread.start()

    game_dir = args.game_jar.resolve().parent
    if args.fightingice_mode == "lightweight":
        classpath = "FightingICE.jar:./lib/*:./lib/lwjgl/*"
        processing_flag = "--lightweight-mode"
    else:
        classpath = "FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*"
        processing_flag = "--headless-mode"

    log_handle = game_log.open("w", encoding="utf-8")
    fightingice = subprocess.Popen(
        [
            "java", "-cp", classpath, "Main",
            processing_flag, "--pyftg-mode", "--input-sync",
            "--limithp", str(args.max_hp), str(args.max_hp),
            "--port", str(args.game_port), "-r", str(rounds_per_session), "-f", "600",
        ],
        cwd=game_dir,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    runner: subprocess.Popen | None = None
    stopping = False

    def terminate(*_):
        nonlocal stopping
        if stopping:
            return
        stopping = True
        stop.set()
        server.shutdown()
        if runner is not None and runner.poll() is None:
            runner.terminate()
        if fightingice.poll() is None:
            fightingice.terminate()

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)

    code = 1
    try:
        wait_for_fightingice(game_log, fightingice)
        run_root = args.out / "runs"
        timeout_seconds = max(900, rounds_per_session * 300)
        command = [
            sys.executable,
            str(Path(__file__).with_name("run_game_malecns_lif.py")),
            "--host", "127.0.0.1", "--port", str(args.game_port),
            "--character-p1", args.p1, "--character-p2", args.p2,
            "--seed-p1", str(args.seed_p1), "--seed-p2", str(args.seed_p2),
            "--reference-python", args.reference_python,
            "--reference-model", str(args.reference_model),
            "--adapter-dir", str(args.adapter_dir),
            "--interface", str(args.interface),
            "--decision-interval", str(args.decision_interval),
            "--games", "1", "--expected-rounds", str(rounds_per_session),
            "--timeout", str(timeout_seconds),
            "--run-id", args.session_id,
            "--out", str(run_root),
            "--live-telemetry-jsonl", str(telemetry_path),
        ]
        if args.adapter_dir_p1:
            command += ["--adapter-dir-p1", str(args.adapter_dir_p1)]
        if args.adapter_dir_p2:
            command += ["--adapter-dir-p2", str(args.adapter_dir_p2)]
        runner = subprocess.Popen(command)
        code = int(runner.wait())
        status_path = run_root / args.session_id / "status.json"
        error = None
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
                error = status.get("error")
            except Exception:
                error = None
        state.finish(code, error)
        if code != 0:
            log_handle.flush()
            print(
                json.dumps(
                    {
                        "kind": "arena-runner-exit",
                        "exit_code": code,
                        "error": error,
                        "fightingice_log_tail": log_tail(game_log),
                    },
                    separators=(",", ":"),
                ),
                file=sys.stderr,
                flush=True,
            )
        hold_observable(args.post_fight_seconds, lambda: stopping)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        state.finish(1, message)
        code = 1
        log_handle.flush()
        print(
            json.dumps(
                {
                    "kind": "arena-runtime-error",
                    "error": message,
                    "fightingice_log_tail": log_tail(game_log),
                },
                separators=(",", ":"),
            ),
            file=sys.stderr,
            flush=True,
        )
        hold_observable(args.post_fight_seconds, lambda: stopping)
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        if runner is not None and runner.poll() is None:
            runner.terminate()
        if fightingice.poll() is None:
            fightingice.terminate()
        try:
            fightingice.wait(timeout=5)
        except subprocess.TimeoutExpired:
            fightingice.kill()
        log_handle.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
