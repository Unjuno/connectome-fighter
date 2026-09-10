"""Audit a completed pair of FightingICE trace files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from connectome_fighter.match_audit import audit_pair


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("p1", type=Path)
    parser.add_argument("p2", type=Path)
    parser.add_argument("--expected-rounds", type=int)
    args = parser.parse_args()
    print(json.dumps(audit_pair(args.p1, args.p2, args.expected_rounds), indent=2))


if __name__ == "__main__":
    main()
