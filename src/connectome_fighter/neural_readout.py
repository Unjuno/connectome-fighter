"""Project-defined temporal readouts for MaleCNS output-group spike counts.

These readouts are interface engineering. They do not claim biological motor
semantics and they never inspect FightingICE state. The wrapped MaleCNS/Shiu
policy remains the only source of neural activity.
"""
from __future__ import annotations

from typing import Any

from .contracts import Action, Decision

READOUT_MODES = ("canonical", "delta", "ema-residual")
GROUP_ORDER = ("FORWARD", "BACKWARD", "UP", "DOWN", "A", "B", "C")


class TemporalReadoutPolicy:
    """Convert existing neural output-group counts into actions using neural history.

    ``canonical`` preserves the wrapped policy action. ``delta`` selects the
    largest positive change since the previous decision. ``ema-residual`` selects
    the largest positive residual from an exponential moving baseline. No game
    coordinates, HP, engine actions, pixels, or non-delay state are used.
    """

    def __init__(self, base, mode: str, *, ema_alpha: float = 0.1):
        if mode not in READOUT_MODES:
            raise ValueError(f"unsupported readout mode: {mode}")
        if not 0.0 < float(ema_alpha) <= 1.0:
            raise ValueError("ema_alpha must be in (0, 1]")
        self.base = base
        self.mode = mode
        self.ema_alpha = float(ema_alpha)
        self.version = base.version if mode == "canonical" else f"{base.version}-readout-{mode}-v1"
        self.previous: dict[str, float] | None = None
        self.ema: dict[str, float] | None = None
        self._last: dict[str, Any] | None = None

    @property
    def worker_ready(self):
        return self.base.worker_ready

    def set_context(self, **kwargs) -> None:
        context_fn = getattr(self.base, "set_context", None)
        if callable(context_fn):
            context_fn(**kwargs)

    def reset(self) -> None:
        self.base.reset()
        self.previous = None
        self.ema = None
        self._last = None

    def _counts(self, brain: dict[str, Any]) -> dict[str, float]:
        counts = brain.get("group_spike_counts")
        if not isinstance(counts, dict):
            raise RuntimeError("MaleCNS telemetry is missing group_spike_counts")
        try:
            current = {name: float(counts[name]) for name in GROUP_ORDER}
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("invalid MaleCNS group_spike_counts") from exc
        return current

    def _temporal_action(self, current: dict[str, float]) -> tuple[int, dict[str, float]]:
        residual = {name: 0.0 for name in GROUP_ORDER}
        if self.mode == "delta":
            if self.previous is not None:
                residual = {name: current[name] - self.previous[name] for name in GROUP_ORDER}
            self.previous = dict(current)
        elif self.mode == "ema-residual":
            if self.ema is None:
                self.ema = dict(current)
            else:
                residual = {name: current[name] - self.ema[name] for name in GROUP_ORDER}
                a = self.ema_alpha
                self.ema = {name: (1.0 - a) * self.ema[name] + a * current[name] for name in GROUP_ORDER}
        else:
            raise RuntimeError("temporal action requested for canonical mode")
        best = max(GROUP_ORDER, key=lambda name: (residual[name], -GROUP_ORDER.index(name)))
        action = int(Action[best]) if residual[best] > 0.0 else int(Action.NEUTRAL)
        return action, residual

    def act(self, observation) -> Decision:
        raw = self.base.act(observation)
        brain = dict(self.base.telemetry() or {})
        current = self._counts(brain)
        if self.mode == "canonical":
            applied = int(raw.action)
            residual = None
        else:
            applied, residual = self._temporal_action(current)
        brain.update({
            "readout_contract": "malecns-temporal-readout-v1",
            "readout_mode": self.mode,
            "readout_ema_alpha": self.ema_alpha if self.mode == "ema-residual" else None,
            "raw_worker_action": int(raw.action),
            "applied_action": int(applied),
            "readout_residual": residual,
            "readout_game_state_used": False,
        })
        self._last = brain
        return Decision(int(applied), 0.0, 0.0, self.version)

    def telemetry(self):
        return self._last

    def close(self) -> None:
        self.base.close()
