"""Validation at the collection/learner boundary. This is NOT a PPO trainer."""
from __future__ import annotations

def validate_training_batch(rounds: list[dict], policy_version: str) -> None:
    if not rounds:
        raise ValueError("An empty batch is not a training result")
    for episode in rounds:
        if (episode.get("kind") != "round" or not episode.get("trainable") or
            not episode.get("terminated") or episode.get("truncated")):
            raise ValueError("Only completed, nonempty rounds are permitted in v0 training")
        steps = episode["transitions"]
        if any(s["policy_version"] != policy_version for s in steps):
            raise ValueError("Stale or mixed behavior-policy versions")
        if any(s["reward"] != 0 for s in steps[:-1]):
            raise ValueError("Main experiment is terminal-only; shaping needs a separate condition")
        if steps[-1]["reward"] != episode["outcome_reward"]:
            raise ValueError("Terminal reward mismatch")
