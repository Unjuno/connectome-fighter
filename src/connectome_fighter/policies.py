from __future__ import annotations
import math
import numpy as np
from .contracts import Decision, N_ACTIONS

class RandomPolicy:
    """An engineering baseline, never described as a connectome."""
    def __init__(self, seed: int, version: str | None = None):
        self.rng = np.random.default_rng(seed)
        self.version = version or f"random-seed-{seed}"

    def reset(self) -> None:
        pass

    def act(self, observation: np.ndarray) -> Decision:
        return Decision(int(self.rng.integers(N_ACTIONS)), -math.log(N_ACTIONS), 0.0, self.version)
