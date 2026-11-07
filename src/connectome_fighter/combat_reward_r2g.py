"""R2g: local combat credit, independent frozen R2e performance objective.

A completed real FightingICE round still supplies the R2e scorer and all
canonical input checks. KC-MBON modulation uses only observed HP changes and
the original, bounded engagement potential. No terminal signal and no
action-specific or synthetic neural rewards are introduced.
"""
from __future__ import annotations

import math

from connectome_fighter import combat_reward as r2e

REWARD_ID = "R2g-local-damage-credit-v1"
CREDIT = {
    "terminal_win_loss_gain": 0.0,
    "terminal_ko_bonus_gain": 0.0,
    "ordinary_draw_credit": 0.0,
    "no_damage_draw_credit": 0.0,
}


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError("R2g must be a JSON object")
    if config.get("schema_version") != 1 or config.get("id") != REWARD_ID:
        raise ValueError("R2g identity changed without explicit version")
    if config.get("status") != "active-candidate-training-not-approved-inference":
        raise ValueError("R2g is restricted to experimental candidate training")
    if config.get("source_reward_id") != r2e.REWARD_ID or config.get("evaluation_reward_id") != r2e.REWARD_ID:
        raise ValueError("R2g external performance objective must remain R2e")
    if config.get("automatic_promotion") is not False or config.get("no_action_specific_reward") is not True:
        raise ValueError("R2g must not authorize promotion or action rewards")
    r2e.validate_config(config.get("base_reward"))
    raw = config.get("training_credit")
    if not isinstance(raw, dict) or set(raw) != set(CREDIT):
        raise ValueError("R2g credit terms require explicit version")
    for key, expected in CREDIT.items():
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or float(value) != expected:
            raise ValueError("R2g terminal credit coefficient changed without version bump")


def rebalance_events(events: list[dict], config: dict) -> list[dict]:
    validate_config(config)
    if not isinstance(events, list) or not events:
        raise ValueError("missing canonical R2e event sequence")
    result=[]
    for i, event in enumerate(events):
        terminal_position = i == len(events) - 1
        if not isinstance(event, dict) or event.get("last") is not terminal_position:
            raise ValueError("invalid canonical terminal decision")
        keys = ("damage_reward", "potential_reward", "terminal_reward", "finish_bonus", "signal")
        vals = {}
        for key in keys:
            v=event.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError("malformed canonical reward components")
            vals[key] = float(v)
        if not math.isclose(vals["signal"], sum(vals[k] for k in keys[:-1]), rel_tol=0, abs_tol=1e-10):
            raise ValueError("unverified R2e event signal sum")
        if not terminal_position and (vals["terminal_reward"] != 0 or vals["finish_bonus"] != 0):
            raise ValueError("terminal modulation before last decision")
        if terminal_position and vals["terminal_reward"] not in (2.0, -2.0, -0.05, -0.25):
            raise ValueError("invalid canonical terminal outcome")
        if vals["finish_bonus"] < 0 or vals["finish_bonus"] > 0.25:
            raise ValueError("KO timing signal out of bounds")
        if vals["finish_bonus"] and (not terminal_position or vals["terminal_reward"] != 2):
            raise ValueError("KO timing bonus only belongs to terminal win")
        adjusted = dict(event)
        adjusted["canonical_r2e_signal"] = vals["signal"]
        adjusted["canonical_terminal_reward"] = vals["terminal_reward"]
        adjusted["terminal_reward"] = 0.0
        adjusted["finish_bonus"] = 0.0
        adjusted["signal"] = vals["damage_reward"] + vals["potential_reward"]
        adjusted["learning_reward_id"] = REWARD_ID
        result.append(adjusted)
    return result


def reward_sequence(round_row: dict, side: int, config: dict, *, require_trainable: bool = True) -> list[dict]:
    validate_config(config)
    events = r2e.reward_sequence(round_row, side, config["base_reward"], require_trainable=require_trainable)
    return rebalance_events(events, config)


def evaluation_utility(metrics: dict, config: dict) -> float:
    validate_config(config)
    return r2e.paired_evaluation_utility(metrics, config["base_reward"])


def evaluation_suite_gate(cases: list[dict], config: dict) -> dict:
    validate_config(config)
    return r2e.paired_evaluation_suite_gate(cases, config["base_reward"])
