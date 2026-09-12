#!/usr/bin/env python3
"""Publish official FightingICE ScreenData as a spectator-only latest PNG."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectome_fighter.fightingice_live_frame import FightingICELiveFramePublisher


async def serve(args: argparse.Namespace) -> None:
    from pyftg.socket.aio.gateway import Gateway

    publisher = FightingICELiveFramePublisher(args.output, fps=args.fps, downsample=args.downsample)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                loop.add_signal_handler(sig, stopped.set)
            except NotImplementedError:
                pass

    failures = 0
    while not stopped.is_set():
        gateway = Gateway(host=args.host, port=args.port)
        gateway.register_stream(publisher)
        try:
            await gateway.start_stream(keep_alive=False)
            failures = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failures += 1
            print(json.dumps({
                "kind": "live-screen-stream-retry",
                "failure": failures,
                "error": f"{type(exc).__name__}: {exc}",
            }, separators=(",", ":")), file=sys.stderr, flush=True)
        finally:
            try:
                await asyncio.wait_for(gateway.close(), timeout=3)
            except Exception:
                pass
        if stopped.is_set():
            break
        await asyncio.sleep(min(2.0, 0.15 * max(1, failures)))

    print(json.dumps({"kind": "live-screen-publisher-stop", **publisher.summary()}, separators=(",", ":")), flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=31415)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fps", type=float, default=10.0)
    p.add_argument("--downsample", type=int, default=2)
    args = p.parse_args()
    if not 1 <= args.port <= 65535:
        p.error("invalid port")
    if args.fps <= 0 or not 1 <= args.downsample <= 8:
        p.error("invalid fps/downsample")
    asyncio.run(serve(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
