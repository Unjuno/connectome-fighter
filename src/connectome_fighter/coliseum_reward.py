"""Audited combat reward. Game units are explicit; no action/spike/animation bonuses.

For complete finite-horizon rounds only. Undiscounted engagement shaping has
zero terminal potential, so its sum depends on the starting state, not the path.
This algebra does not establish convergence of the valence plasticity learner.
"""
from __future__ import annotations

import math
from typing import Any

REWARD_ID = "COLISEUM-v1"


def finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def natural(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def validate_config(cfg: dict) -> None:
    if cfg.get("id") != REWARD_ID:
        raise ValueError("wrong Coliseum reward identity")
    damage = cfg["damage"]
    if finite(damage["unit_hp"], "maximum HP") != 400 or finite(damage["weight_per_unit"], "damage weight") != 1:
        raise ValueError("COLISEUM-v1 damage scale changed; create a new version")
    if cfg["terminal"] != {"win": 2.0, "loss": -2.0, "ordinary_draw": 0.0, "no_damage_draw_penalty": -0.05}:
        raise ValueError("COLISEUM-v1 terminal coefficients changed")
    pot = cfg["engagement_potential"]
    if pot != {"enabled": True, "contact_band_px": 180.0, "stage_width_px": 960.0, "weight": 0.05, "terminal_potential": 0.0}:
        raise ValueError("COLISEUM-v1 potential contract changed")
    if cfg["control"] != {"decision_interval_frames": 30, "biological_window_ms": 20, "round_frame_limit": 3600, "nominal_game_fps": 60}:
        raise ValueError("COLISEUM-v1 control protocol changed")


def potential(distance: float, cfg: dict) -> float:
    p = cfg["engagement_potential"]
    # Clamp the engineering potential, not the underlying game observation.
    return -min(1.0, max(0.0, distance - p["contact_band_px"]) / p["stage_width_px"])


def reward_sequence(round_row: dict, side: int, cfg: dict) -> list[dict]:
    validate_config(cfg)
    if type(side) is not int or side not in (0, 1):
        raise ValueError("side must be 0 or 1")
    if (round_row.get("kind") != "round" or round_row.get("terminated") is not True
        or round_row.get("truncated") is not False or round_row.get("trainable") is not True
        or round_row.get("player_index") != side):
        raise ValueError("only matching, completed, trainable rounds may update weights")
    ts = round_row.get("transitions")
    terminal = round_row.get("remaining_hps")
    if not isinstance(ts, list) or not ts or not isinstance(terminal, list) or len(terminal) != 2:
        raise ValueError("missing transitions or terminal HP")
    maximum = float(cfg["damage"]["unit_hp"])
    def health(value):
        value = finite(value, "HP")
        if not 0 <= value <= maximum:
            raise ValueError("HP outside configured bounds")
        return value
    terminal = [health(v) for v in terminal]
    elapsed = natural(round_row.get("elapsed_frame"), "terminal frame")
    if elapsed <= 0 or elapsed > cfg["control"]["round_frame_limit"]:
        raise ValueError("terminal frame outside protocol")
    if min(terminal) > 0 and elapsed != cfg["control"]["round_frame_limit"]:
        raise ValueError("early non-KO round is incomplete")
    frames, indices, hp_rows, distances = [], [], [], []
    for t in ts:
        frames.append(natural(t.get("frame"), "frame"))
        indices.append(natural((t.get("brain") or {}).get("trace_decision_index"), "decision index"))
        display = t.get("display") or {}
        a, b = display.get("p1") or {}, display.get("p2") or {}
        hp_rows.append([health(a.get("hp")), health(b.get("hp"))])
        distances.append(abs(finite(a.get("x"), "p1 x") - finite(b.get("x"), "p2 x")))
    if any(b <= a for a, b in zip(frames, frames[1:])) or any(b <= a for a, b in zip(indices, indices[1:])):
        raise ValueError("decision frames and indices must advance strictly")
    if frames[-1] >= elapsed:
        raise ValueError("decision must precede terminal outcome")
    # The first observed HP need not be 400: use actual recorded deltas, never
    # invent unobserved damage. Delayed observation can hide early damage.
    all_hp = hp_rows + [terminal]
    for before, after in zip(all_hp, all_hp[1:]):
        if any(b > a for a, b in zip(before, after)):
            raise ValueError("healing or HP reset is outside this protocol")
    events, total_damage = [], 0.0
    for i, (before, after) in enumerate(zip(all_hp, all_hp[1:])):
        dealt = before[1-side] - after[1-side]
        taken = before[side] - after[side]
        total_damage += dealt + taken
        damage = cfg["damage"]["weight_per_unit"] * (dealt - taken) / maximum
        next_phi = 0.0 if i == len(ts)-1 else potential(distances[i+1], cfg)
        shaping = cfg["engagement_potential"]["weight"] * (next_phi - potential(distances[i], cfg))
        events.append({"decision_index": indices[i], "frame": frames[i],
                       "damage_dealt_hp": dealt, "damage_taken_hp": taken,
                       "damage_reward": damage, "potential_reward": shaping,
                       "terminal_reward": 0.0, "signal": damage + shaping, "last": i == len(ts)-1})
    margin = terminal[side] - terminal[1-side]
    # If either player already has missing HP in the first recorded state,
    # this is not a no-damage round, even when later deltas are all zero.
    no_damage = total_damage == 0 and terminal == [maximum, maximum]
    key = "win" if margin > 0 else "loss" if margin < 0 else "no_damage_draw_penalty" if no_damage else "ordinary_draw"
    events[-1]["terminal_reward"] = float(cfg["terminal"][key])
    events[-1]["signal"] += float(cfg["terminal"][key])
    return events
