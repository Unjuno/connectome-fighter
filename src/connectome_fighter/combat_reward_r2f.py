"""Isolated R2f candidate: balanced *learning credit*, unchanged R2e evaluation.

This is an engineering experiment on the MaleCNS/Shiu system, not an identified
Drosophila reward pathway or evidence of improved game skill.
"""
from __future__ import annotations

import math

from connectome_fighter import combat_reward as r2e

REWARD_ID = "R2f-credit-balanced-v1"
CREDIT = {
    "terminal_win_loss_gain": 0.5,
    "terminal_ko_bonus_gain": 0.5,
    "ordinary_draw_credit": 0.0,
    "no_damage_draw_credit": 0.0,
}


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError("R2f config must be an object")
    if config.get("schema_version") != 1 or config.get("id") != REWARD_ID:
        raise ValueError("R2f schema / reward identity mismatch")
    if config.get("status") != "research-only-unvalidated-not-canonical":
        raise ValueError("R2f must remain an unvalidated research candidate")
    if config.get("source_reward_id") != r2e.REWARD_ID:
        raise ValueError("R2f source reward mismatch")
    if config.get("evaluation_reward_id") != r2e.REWARD_ID:
        raise ValueError("R2f evaluation must use unchanged R2e utility")
    if config.get("automatic_promotion") is not False:
        raise ValueError("R2f cannot authorize automatic promotion")
    if config.get("no_action_specific_reward") is not True:
        raise ValueError("action-specific reward is not allowed")
    base = config.get("base_reward")
    r2e.validate_config(base)
    credit = config.get("training_credit")
    if not isinstance(credit, dict) or set(credit) != set(CREDIT):
        raise ValueError("R2f credit terms require an explicit new version")
    for key, expected in CREDIT.items():
        actual = credit[key]
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual) or float(actual) != expected:
            raise ValueError("R2f credit value changed without a reward version change")


def rebalance_events(events: list[dict], config: dict) -> list[dict]:
    """Reallocate training modulation without changing local damage or proximity.

    Only inputs already validated by the canonical R2e scorer are suitable.
    The function separately checks the components and terminal placement to
    prevent a raw, incomplete or tampered event stream being used as training.
    """
    validate_config(config)
    if not isinstance(events, list) or not events:
        raise ValueError("empty canonical event stream")
    new_events = []
    for i, event in enumerate(events):
        if not isinstance(event, dict) or event.get("last") is not (i == len(events) - 1):
            raise ValueError("non-canonical terminal placement")
        values = {}
        for key in ("damage_reward", "potential_reward", "terminal_reward", "finish_bonus", "signal"):
            val = event.get(key)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError("non-finite / malformed canonical reward component")
            values[key] = float(val)
        if not math.isclose(
            values["signal"],
            sum(values[k] for k in ("damage_reward", "potential_reward", "terminal_reward", "finish_bonus")),
            rel_tol=0.0, abs_tol=1e-10,
        ):
            raise ValueError("canonical reward components disagree with logged signal")
        if i < len(events) - 1 and (values["terminal_reward"] != 0 or values["finish_bonus"] != 0):
            raise ValueError("terminal credit outside final decision")
        terminal = values["terminal_reward"]
        if i == len(events) - 1:
            if terminal in (2.0, -2.0):
                new_terminal = terminal * CREDIT["terminal_win_loss_gain"]
            elif terminal == -0.05:
                new_terminal = CREDIT["ordinary_draw_credit"]
            elif terminal == -0.25:
                new_terminal = CREDIT["no_damage_draw_credit"]
            else:
                raise ValueError("unrecognized R2e terminal outcome")
            new_bonus = values["finish_bonus"] * CREDIT["terminal_ko_bonus_gain"]
        else:
            new_terminal = 0.0
            new_bonus = 0.0
        if values["finish_bonus"] < 0 or values["finish_bonus"] > 0.25:
            raise ValueError("KO finish bonus outside canonical bounds")
        if values["finish_bonus"] and terminal != 2.0:
            raise ValueError("KO finish bonus requires a win")
        changed = dict(event)
        changed["canonical_r2e_signal"] = values["signal"]
        changed["canonical_terminal_reward"] = terminal
        changed["terminal_reward"] = new_terminal
        changed["finish_bonus"] = new_bonus
        changed["signal"] = values["damage_reward"] + values["potential_reward"] + new_terminal + new_bonus
        changed["learning_reward_id"] = REWARD_ID
        new_events.append(changed)
    return new_events


def reward_sequence(round_row: dict, side: int, config: dict, *, require_trainable: bool = True) -> list[dict]:
    validate_config(config)
    canonical = r2e.reward_sequence(
        round_row, side, config["base_reward"], require_trainable=require_trainable
    )
    return rebalance_events(canonical, config)


def evaluation_utility(metrics: dict, config: dict) -> float:
    """Keep the independent fighting-performance selection target unchanged."""
    validate_config(config)
    return r2e.paired_evaluation_utility(metrics, config["base_reward"])


def evaluation_suite_gate(cases: list[dict], config: dict) -> dict:
    validate_config(config)
    return r2e.paired_evaluation_suite_gate(cases, config["base_reward"])
