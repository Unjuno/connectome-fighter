"""Versioned game reward for completed, audited colosseum rounds.

Engineering reward, not an endogenous fly reinforcement signal. The existing
KC->MBON updater is nonlinear and sign-sensitive: no policy-invariance or
learning-convergence guarantee is claimed. HP and pixels are game units.
"""
from __future__ import annotations

import math
from typing import Any

REWARD_ID = "R3-colosseum-v1"


def number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: numeric value required")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{label}: finite value >= {minimum} required")
    return result


def validate_config(config: dict[str, Any]) -> None:
    if config.get("id") != REWARD_ID or config.get("schema_version") != 1:
        raise ValueError("unsupported colosseum reward identity")
    if config.get("discount") != 1.0:
        raise ValueError("this finite-round reward uses undiscounted signals")
    if config.get("terminal_potential") != 0.0:
        raise ValueError("terminal potential must be zero")
    for key in ("max_hp", "stage_width_px"):
        if number(config.get(key), key) <= 0:
            raise ValueError(f"{key} must be positive")
    for key in ("damage_weight", "engagement_weight", "contact_band_px"):
        number(config.get(key), key)
    terminal = config.get("terminal", {})
    for key in ("win", "loss", "draw", "no_damage_draw"):
        number(terminal.get(key), key, minimum=-10.0)
    if not (terminal["win"] > 0 > terminal["draw"] >= terminal["no_damage_draw"] > terminal["loss"]):
        raise ValueError("terminal ranking must be win > 0 > draw >= no-damage draw > loss")
    if config["damage_weight"] + config["engagement_weight"] >= terminal["win"]:
        raise ValueError("auxiliary terms must not dominate winning")
    if config["engagement_weight"] >= -terminal["no_damage_draw"]:
        raise ValueError("movement alone must not wash out the no-damage penalty")


def potential(distance_px: float, config: dict[str, Any]) -> float:
    width = config["stage_width_px"]
    # Bounded independently of unusual game positions; no reward for oscillations.
    return -min(max(distance_px - config["contact_band_px"], 0.0) / width, 1.0)


def reward_sequence(round_row: dict[str, Any], side: int, config: dict[str, Any]) -> list[dict[str, Any]]:
    validate_config(config)
    if type(side) is not int or side not in (0, 1):
        raise ValueError("side must be zero-based player 0 or 1")
    if (round_row.get("kind") != "round" or round_row.get("terminated") is not True
            or round_row.get("truncated") is not False or round_row.get("trainable") is not True
            or round_row.get("player_index") != side):
        raise ValueError("only completed, non-truncated, explicitly trainable player traces are accepted")
    transitions = round_row.get("transitions")
    terminal = round_row.get("remaining_hps")
    if not isinstance(transitions, list) or not transitions or not isinstance(terminal, list) or len(terminal) != 2:
        raise ValueError("missing transition or terminal record")
    hmax = config["max_hp"]
    # FightingICE may report negative HP after a KO. Clamp only that overkill.
    terminal_hp = [max(0.0, number(v, "terminal HP", minimum=-hmax)) for v in terminal]
    if max(terminal_hp) > hmax:
        raise ValueError("terminal HP exceeds configured initial HP")
    states: list[tuple[list[float], float, int, int]] = []
    for t in transitions:
        display, brain = t.get("display"), t.get("brain")
        if not isinstance(display, dict) or not isinstance(brain, dict):
            raise ValueError("display and canonical brain trace required")
        frame, decision = t.get("frame"), brain.get("trace_decision_index")
        if type(frame) is not int or frame < 0 or type(decision) is not int or decision < 0:
            raise ValueError("invalid frame/decision identity")
        if states and (frame <= states[-1][2] or decision <= states[-1][3]):
            raise ValueError("frames and decisions must increase strictly")
        hp = [max(0.0, number(display[p]["hp"], "HP", minimum=-hmax)) for p in ("p1", "p2")]
        if max(hp) > hmax:
            raise ValueError("HP exceeds configured initial HP")
        x = [number(display[p]["x"], "x", minimum=-config["stage_width_px"]) for p in ("p1", "p2")]
        states.append((hp, abs(x[0] - x[1]), frame, decision))
    elapsed = round_row.get("elapsed_frame")
    if type(elapsed) is not int or elapsed < states[-1][2]:
        raise ValueError("terminal frame precedes the final decision")
    events: list[dict[str, Any]] = []
    total_dealt = total_taken = 0.0
    for i, (hp0, distance0, frame, decision) in enumerate(states):
        last = i == len(states) - 1
        hp1 = terminal_hp if last else states[i + 1][0]
        if any(b > a + 1e-9 for a, b in zip(hp0, hp1)):
            raise ValueError("HP increased within a round; reset/healing requires a new reward contract")
        dealt, taken = hp0[1-side] - hp1[1-side], hp0[side] - hp1[side]
        total_dealt += dealt; total_taken += taken
        after_potential = 0.0 if last else potential(states[i+1][1], config)
        shaping = config["engagement_weight"] * (after_potential - potential(distance0, config))
        damage = config["damage_weight"] * (dealt - taken) / hmax
        events.append({"decision_index": decision, "frame": frame,
                       "damage_dealt_hp": dealt, "damage_taken_hp": taken,
                       "damage_reward": damage, "potential_reward": shaping,
                       "terminal_reward": 0.0, "signal": damage + shaping, "last": last})
    # Include the initial-to-first-observation interval in the no-damage test.
    no_damage = terminal_hp == [hmax, hmax] and total_dealt + total_taken == 0.0
    margin = terminal_hp[side] - terminal_hp[1-side]
    outcome = "win" if margin > 0 else "loss" if margin < 0 else "no_damage_draw" if no_damage else "draw"
    events[-1]["terminal_reward"] = config["terminal"][outcome]
    events[-1]["signal"] += config["terminal"][outcome]
    events[-1]["outcome"] = outcome
    if not all(math.isfinite(e["signal"]) for e in events):
        raise ValueError("non-finite reward")
    return events
