"""Game-independent contracts. All observations/rewards are dimensionless."""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol
import math
import numpy as np

class Action(IntEnum):
    NEUTRAL = 0
    FORWARD = 1
    BACKWARD = 2
    UP = 3
    DOWN = 4
    A = 5
    B = 6
    C = 7

N_ACTIONS = len(Action)
OBS_DIM = 18
KEY_NAMES = ("A", "B", "C", "U", "R", "D", "L")

def player_index(player_number: bool) -> int:
    # pyftg uses True=P1, False=P2, NOT the usual integers 0=P1, 1=P2.
    if type(player_number) is not bool:
        raise TypeError("pyftg player_number must be bool: True=P1, False=P2")
    return 0 if player_number else 1

def action_keys(action: int, facing_right: bool) -> dict[str, bool]:
    a = Action(action)
    keys = {key: False for key in KEY_NAMES}
    if a == Action.FORWARD:
        keys["R" if facing_right else "L"] = True
    elif a == Action.BACKWARD:
        keys["L" if facing_right else "R"] = True
    elif a in (Action.UP, Action.DOWN, Action.A, Action.B, Action.C):
        key = {Action.UP: "U", Action.DOWN: "D", Action.A: "A", Action.B: "B", Action.C: "C"}[a]
        keys[key] = True
    return keys

@dataclass(frozen=True)
class Observation:
    vector: np.ndarray
    round_id: int
    frame: int
    facing_right: bool

    def __post_init__(self) -> None:
        v = np.asarray(self.vector, dtype=np.float32).copy()
        if v.shape != (OBS_DIM,) or not np.isfinite(v).all():
            raise ValueError(f"Observation must be finite float32[{OBS_DIM}]")
        if self.frame <= 0 or self.round_id < 0:
            raise ValueError("Invalid frame or round identifier")
        v.flags.writeable = False
        object.__setattr__(self, "vector", v)

@dataclass(frozen=True)
class Decision:
    action: int
    log_prob: float
    value: float
    policy_version: str

    def __post_init__(self) -> None:
        Action(self.action)
        if not all(map(math.isfinite, (self.log_prob, self.value))):
            raise ValueError("Non-finite policy output")
        if self.log_prob > 1e-6 or not self.policy_version:
            raise ValueError("Invalid log-probability or missing policy version")

class Policy(Protocol):
    def reset(self) -> None: ...
    def act(self, observation: np.ndarray) -> Decision: ...
