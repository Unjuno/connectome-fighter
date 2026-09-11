from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectome_fighter.state_bundle import restore_state


def main() -> int:
    p = argparse.ArgumentParser(description="Verify and restore an active durable training-state slot")
    p.add_argument("--download-dir", type=Path, required=True)
    p.add_argument("--state-dir", type=Path, required=True)
    args = p.parse_args()
    restored = restore_state(args.download_dir, args.state_dir)
    print(json.dumps(restored, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
