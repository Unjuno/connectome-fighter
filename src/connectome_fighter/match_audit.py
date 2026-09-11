"""Strict two-sided trace auditing; valid traces alone do not prove a real game ran."""
from __future__ import annotations
from collections import Counter
import json
import math
from pathlib import Path
from .contracts import N_ACTIONS, OBS_DIM, action_keys
from .trajectory import round_reward


def _fail(message: str) -> None:
    raise ValueError(message)


def _finite_number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _read(path: Path, side: int, expected_trainable: bool | None) -> dict:
    rounds = {}
    if not path.is_file():
        _fail(f"Missing P{side+1} trace: {path}")
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("kind") != "round":
                _fail(f"P{side+1} line {number}: incomplete/aborted record; not a completed match")
            if item.get("player_index") != side:
                _fail("Player-side mismatch")
            if item.get("terminated") is not True or item.get("truncated") is not False:
                _fail("Invalid termination flags")
            if type(item.get("trainable")) is not bool:
                _fail("Missing trainable/evaluation trace flag")
            if expected_trainable is not None and item["trainable"] is not expected_trainable:
                mode = "trainable" if expected_trainable else "frozen evaluation"
                _fail(f"Round does not match expected {mode} trace mode")
            identity = (item.get("match_id"), item.get("round_id"))
            if not isinstance(identity[0], str) or not identity[0] or type(identity[1]) is not int:
                _fail("Invalid round identity")
            if identity in rounds:
                _fail("Duplicate round")
            hp = item.get("remaining_hps")
            expected = round_reward(hp, side == 0)
            if item.get("outcome_reward") != expected:
                _fail("Terminal reward disagrees with remaining HP")
            if type(item.get("elapsed_frame")) is not int or item["elapsed_frame"] <= 0:
                _fail("Invalid terminal frame")
            transitions = item.get("transitions")
            if not isinstance(transitions, list) or not transitions:
                _fail("Missing decisions")
            previous = 0
            version = None
            for index, step in enumerate(transitions):
                frame = step.get("frame")
                if type(frame) is not int or not previous < frame <= item["elapsed_frame"]:
                    _fail("Invalid decision-frame order")
                previous = frame
                obs = step.get("observation")
                if not isinstance(obs, list) or len(obs) != OBS_DIM or not all(map(_finite_number, obs)):
                    _fail("Invalid observation vector")
                action = step.get("action")
                if type(action) is not int or not 0 <= action < N_ACTIONS:
                    _fail("Invalid action")
                for name in ("log_prob", "value", "reward"):
                    if not _finite_number(step.get(name)):
                        _fail(f"Non-finite/missing {name}")
                if step["log_prob"] > 1e-6:
                    _fail("Positive discrete log-probability")
                if not step.get("policy_version"):
                    _fail("Missing policy version")
                if version is None:
                    version = step["policy_version"]
                elif version != step["policy_version"]:
                    _fail("Policy changed within a round")
                reward = expected if index == len(transitions)-1 else 0.0
                if step["reward"] != reward:
                    _fail("Reward must appear only on the final decision")
                if "requested_keys" in step:
                    facing = step.get("facing_right")
                    if type(facing) is not bool:
                        _fail("Missing direction for key reconstruction")
                    if step["requested_keys"] != action_keys(action, facing):
                        _fail("Requested keys disagree with action/direction")
            rounds[identity] = item
    if not rounds:
        _fail("No completed rounds")
    return rounds


def audit_pair(
    p1: Path,
    p2: Path,
    expected_rounds: int | None = None,
    *,
    expected_trainable: bool | None = True,
) -> dict:
    """Audit two-sided traces.

    `expected_trainable=True` preserves the original integration-training gate.
    Frozen canonical evaluation/smoke matches must explicitly pass False; None
    accepts either mode but still requires both sides to agree.
    """
    left, right = (
        _read(p1, 0, expected_trainable),
        _read(p2, 1, expected_trainable),
    )
    if left.keys() != right.keys():
        _fail("P1/P2 round identities differ")
    if expected_rounds is not None and len(left) != expected_rounds:
        _fail(f"Expected {expected_rounds} rounds, received {len(left)}")
    summary = []
    for identity, a in left.items():
        b = right[identity]
        if a["trainable"] is not b["trainable"]:
            _fail("P1/P2 disagree on trainable/evaluation mode")
        for name in ("remaining_hps", "elapsed_frame"):
            if a[name] != b[name]:
                _fail(f"P1/P2 disagree on {name}")
        if a["outcome_reward"] + b["outcome_reward"] != 0:
            _fail("Reward is not zero-sum")
        if a["opponent_version"] != b["transitions"][0]["policy_version"]:
            _fail("P1 opponent version mismatch")
        if b["opponent_version"] != a["transitions"][0]["policy_version"]:
            _fail("P2 opponent version mismatch")
        summary.append({
            "match_id": identity[0], "round_id": identity[1], "remaining_hps": a["remaining_hps"],
            "rewards": [a["outcome_reward"], b["outcome_reward"]], "elapsed_frame": a["elapsed_frame"],
            "decisions": [len(a["transitions"]), len(b["transitions"])],
            "trainable": a["trainable"],
        })
    histogram = []
    for group in (left, right):
        counts = Counter(str(step["action"]) for item in group.values() for step in item["transitions"])
        histogram.append(dict(sorted(counts.items())))
    return {
        "status": "VALID_LOG_CONTRACT",
        "rounds": summary,
        "completed_rounds_per_agent": [len(left), len(right)],
        "action_histograms": histogram,
        "learning_performed": bool(summary and summary[0]["trainable"]),
        "note": "Log validation is not independent evidence of engine identity or applied-key timing.",
    }
