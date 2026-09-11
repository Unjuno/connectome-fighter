from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectome_fighter.state_bundle import package_state


def main() -> int:
    p = argparse.ArgumentParser(description="Package the inactive durable training-state slot")
    p.add_argument("--state-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    pointer = package_state(args.state_dir, args.out)
    print(json.dumps(pointer, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
