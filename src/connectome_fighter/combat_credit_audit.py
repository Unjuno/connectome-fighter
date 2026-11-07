"""Fail-closed decomposition of actual R2g post-game learning credit.

This reports measured FightingICE reward attribution only. It does not change
the credit, eligibility traces, neural topology, or candidate acceptance.
"""
from __future__ import annotations

import math

R2G_ID = "R2g-local-damage-credit-v1"
REQUIRED = ("damage_reward", "potential_reward", "terminal_reward",
            "finish_bonus", "signal", "canonical_r2e_signal",
            "canonical_terminal_reward")


def audit_r2g_credit(events: list[dict]) -> dict:
    """Validate and aggregate a canonical-scored, R2g-reweighted event stream."""
    if not isinstance(events, list) or not events:
        raise ValueError("R2g audit requires a nonempty completed event stream")
    sums = {key: 0.0 for key in REQUIRED}
    absolute = {"damage_reward": 0.0, "potential_reward": 0.0, "signal": 0.0}
    counts = {"damage": 0, "potential": 0, "any": 0, "positive": 0, "negative": 0}
    previous_decision = -1
    for i, event in enumerate(events):
        if not isinstance(event, dict) or event.get("learning_reward_id") != R2G_ID:
            raise ValueError("R2g audit has a different or missing learning-credit identity")
        if event.get("last") is not (i == len(events) - 1):
            raise ValueError("R2g audit requires a terminal event only at the last decision")
        idx = event.get("decision_index")
        if isinstance(idx, bool) or not isinstance(idx, int) or idx <= previous_decision:
            raise ValueError("R2g audit requires strictly increasing decision identities")
        previous_decision = idx
        values = {}
        for key in REQUIRED:
            value = event.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("R2g audit requires finite canonical signal components")
            values[key] = float(value)
            sums[key] += float(value)
        if values["terminal_reward"] != 0.0 or values["finish_bonus"] != 0.0:
            raise ValueError("R2g local credit cannot contain terminal modulation")
        if not math.isclose(values["signal"], values["damage_reward"] + values["potential_reward"],
                            rel_tol=0, abs_tol=1e-10):
            raise ValueError("R2g signal differs from observed local credit")
        if not math.isclose(values["canonical_r2e_signal"],
                            values["damage_reward"] + values["potential_reward"]
                            + values["canonical_terminal_reward"] + (event.get("canonical_finish_bonus", 0.0)),
                            rel_tol=0, abs_tol=1e-10):
            # R2g events retain the original KO bonus only indirectly: before
            # the current reward conversion the KO bonus is not recorded.
            # Nonzero difference can only occur at a verified terminal win.
            diff = values["canonical_r2e_signal"] - (
                values["damage_reward"] + values["potential_reward"]
                + values["canonical_terminal_reward"])
            if not (i == len(events)-1 and values["canonical_terminal_reward"] == 2.0
                    and -1e-10 <= diff <= 0.25 + 1e-10):
                raise ValueError("unverified original terminal KO contribution")
        for key in absolute:
            absolute[key] += abs(values[key])
        counts["damage"] += values["damage_reward"] != 0
        counts["potential"] += values["potential_reward"] != 0
        counts["any"] += values["signal"] != 0
        counts["positive"] += values["signal"] > 0
        counts["negative"] += values["signal"] < 0
    # Under R2g, terminal component is zero; differences between real R2e and
    # R2g reflect only removed completion and optional winning-KO bonuses.
    inferred_ko = sums["canonical_r2e_signal"] - sums["signal"] - sums["canonical_terminal_reward"]
    if not -1e-9 <= inferred_ko <= 0.25 + 1e-9:
        raise ValueError("canonical-to-R2g terminal difference inconsistent")
    return {
        "schema_version": 1,
        "learning_credit_id": R2G_ID,
        "decision_windows": len(events),
        "damage_window_count": counts["damage"],
        "potential_window_count": counts["potential"],
        "nonzero_modulation_windows": counts["any"],
        "positive_windows": counts["positive"],
        "negative_windows": counts["negative"],
        "net_damage_credit": sums["damage_reward"],
        "net_potential_credit": sums["potential_reward"],
        "net_terminal_credit": sums["terminal_reward"],
        "net_modulatory_credit": sums["signal"],
        "canonical_r2e_net_credit": sums["canonical_r2e_signal"],
        "removed_terminal_credit": sums["canonical_terminal_reward"],
        "removed_ko_bonus_credit": max(0.0, inferred_ko),
        "gross_absolute_damage_credit": absolute["damage_reward"],
        "gross_absolute_potential_credit": absolute["potential_reward"],
        "gross_absolute_modulatory_credit": absolute["signal"],
        "causal_boundary": "Attribution of recorded reward components, not proof of per-synapse causal credit or stronger game play.",
    }
