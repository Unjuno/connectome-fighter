#!/usr/bin/env python3
"""Create an isolated research checkpoint for versioned R2f score experiments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectome_fighter.combat_checkpoint import config_from_json
from connectome_fighter.combat_reward_r2f import validate_config
from connectome_fighter.combat_reward_r2f_checkpoint import fork_r2e_to_r2f


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-state", type=Path, required=True)
    p.add_argument("--research-state", type=Path, required=True)
    p.add_argument("--r2e-plasticity", type=Path, default=ROOT / "configs/plasticity_combat_v1.json")
    p.add_argument("--r2f-plasticity", type=Path, default=ROOT / "configs/plasticity_r2f_credit_balanced_v1.json")
    p.add_argument("--r2f-reward", type=Path, default=ROOT / "configs/reward_r2f_credit_balanced_v1.json")
    args = p.parse_args()
    raw = json.loads(args.r2f_reward.read_text(encoding="utf-8"))
    validate_config(raw)
    old = config_from_json(json.loads(args.r2e_plasticity.read_text(encoding="utf-8")))
    new = config_from_json(json.loads(args.r2f_plasticity.read_text(encoding="utf-8")))
    if old.reward_id != raw["source_reward_id"] or new.reward_id != raw["id"]:
        p.error("reward and plasticity identity mismatch")
    receipt = fork_r2e_to_r2f(args.source_state, args.research_state, old, new)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
