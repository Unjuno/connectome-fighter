"""PPO updates for fixed-connectome readout/value heads.

The biological graph and recurrent dynamics are frozen in this milestone. During
live play the controller records descending-neuron features. PPO therefore only
updates the character-specific actor and critic heads from those fixed features.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import math

import numpy as np
import torch
from torch import nn

from .contracts import N_ACTIONS


class ReadoutHeads(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        if input_dim <= 0:
            raise ValueError("input_dim must be positive")
        self.input_dim = int(input_dim)
        self.actor = nn.Linear(self.input_dim, N_ACTIONS)
        self.critic = nn.Linear(self.input_dim, 1)

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.actor(features), self.critic(features).squeeze(-1)


@dataclass(frozen=True)
class PPOConfig:
    learning_rate: float = 3e-4
    gamma: float = 0.995
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    epochs: int = 4
    max_grad_norm: float = 1.0

    def __post_init__(self) -> None:
        if not (0 < self.learning_rate and 0 < self.gamma <= 1 and 0 < self.clip_epsilon < 1):
            raise ValueError("Invalid PPO learning rate/gamma/clip")
        if self.value_coef < 0 or self.entropy_coef < 0 or self.epochs <= 0 or self.max_grad_norm <= 0:
            raise ValueError("Invalid PPO coefficients")

    def as_dict(self) -> dict[str, Any]:
        return {
            "algorithm": "PPO-readout-v1",
            "learning_rate": self.learning_rate,
            "gamma": self.gamma,
            "clip_epsilon": self.clip_epsilon,
            "value_coef": self.value_coef,
            "entropy_coef": self.entropy_coef,
            "epochs": self.epochs,
            "max_grad_norm": self.max_grad_norm,
        }


def make_optimizer(heads: ReadoutHeads, config: PPOConfig) -> torch.optim.Optimizer:
    return torch.optim.Adam(heads.parameters(), lr=config.learning_rate)


def initialize_heads(input_dim: int, seed: int) -> ReadoutHeads:
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        return ReadoutHeads(input_dim)


def _samples(rounds: Iterable[dict[str, Any]], gamma: float) -> tuple[np.ndarray, ...]:
    features: list[list[float]] = []
    actions: list[int] = []
    old_log_probs: list[float] = []
    old_values: list[float] = []
    returns: list[float] = []
    for round_payload in rounds:
        if round_payload.get("kind") != "round" or not round_payload.get("terminated"):
            continue
        transitions = round_payload.get("transitions") or []
        if not transitions:
            continue
        terminal = float(round_payload["outcome_reward"])
        if not math.isfinite(terminal):
            continue
        n = len(transitions)
        for i, t in enumerate(transitions):
            brain = t.get("brain") or {}
            f = brain.get("readout_features")
            if not isinstance(f, list) or not f:
                raise ValueError("Training trace lacks connectome readout_features")
            features.append([float(x) for x in f])
            actions.append(int(t["action"]))
            old_log_probs.append(float(t["log_prob"]))
            old_values.append(float(t["value"]))
            returns.append(terminal * (gamma ** (n - 1 - i)))
    if not features:
        raise ValueError("No trainable connectome transitions")
    widths = {len(x) for x in features}
    if len(widths) != 1:
        raise ValueError("Inconsistent readout feature width")
    return (
        np.asarray(features, dtype=np.float32),
        np.asarray(actions, dtype=np.int64),
        np.asarray(old_log_probs, dtype=np.float32),
        np.asarray(old_values, dtype=np.float32),
        np.asarray(returns, dtype=np.float32),
    )


def ppo_update(
    heads: ReadoutHeads,
    optimizer: torch.optim.Optimizer,
    rounds: Iterable[dict[str, Any]],
    config: PPOConfig,
) -> dict[str, float | int]:
    f_np, a_np, old_lp_np, old_v_np, ret_np = _samples(rounds, config.gamma)
    if f_np.shape[1] != heads.input_dim:
        raise ValueError("Checkpoint/readout dimension differs from trace")
    features = torch.from_numpy(f_np)
    actions = torch.from_numpy(a_np)
    old_log_probs = torch.from_numpy(old_lp_np)
    old_values = torch.from_numpy(old_v_np)
    returns = torch.from_numpy(ret_np)
    advantages = returns - old_values
    if advantages.numel() > 1:
        advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)

    last: dict[str, float] = {}
    for _ in range(config.epochs):
        logits, values = heads(features)
        dist = torch.distributions.Categorical(logits=logits)
        new_log_probs = dist.log_prob(actions)
        ratio = torch.exp(new_log_probs - old_log_probs)
        unclipped = ratio * advantages
        clipped = torch.clamp(ratio, 1 - config.clip_epsilon, 1 + config.clip_epsilon) * advantages
        policy_loss = -torch.minimum(unclipped, clipped).mean()
        value_loss = torch.mean((values - returns) ** 2)
        entropy = dist.entropy().mean()
        loss = policy_loss + config.value_coef * value_loss - config.entropy_coef * entropy
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(heads.parameters(), config.max_grad_norm)
        optimizer.step()
        last = {
            "loss": float(loss.detach()),
            "policy_loss": float(policy_loss.detach()),
            "value_loss": float(value_loss.detach()),
            "entropy": float(entropy.detach()),
            "grad_norm": float(grad_norm),
        }
    last.update({
        "transitions": int(features.shape[0]),
        "rounds": int(sum(1 for _ in [])),  # retained key shape; caller records round count
        "mean_return": float(returns.mean()),
    })
    return last


def apply_heads_to_connectome(heads: ReadoutHeads, model: nn.Module) -> None:
    model.actor.load_state_dict(heads.actor.state_dict())
    model.critic.load_state_dict(heads.critic.state_dict())


def heads_from_connectome(model: nn.Module) -> ReadoutHeads:
    heads = ReadoutHeads(model.actor.in_features)
    heads.actor.load_state_dict(model.actor.state_dict())
    heads.critic.load_state_dict(model.critic.state_dict())
    return heads
