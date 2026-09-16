from __future__ import annotations

import numpy as np
import pytest

from connectome_fighter.contracts import Action, Decision
from connectome_fighter.neural_readout import GROUP_ORDER, TemporalReadoutPolicy


class FakeBase:
    version = "fake-base"
    worker_ready = {"neurons": 156675, "synapses": 6025920}

    def __init__(self, sequence, raw_action=Action.B):
        self.sequence = list(sequence)
        self.raw_action = int(raw_action)
        self.index = 0
        self.last = None
        self.closed = False
        self.context = None

    def set_context(self, **kwargs):
        self.context = dict(kwargs)

    def reset(self):
        self.index = 0
        self.last = None

    def act(self, observation):
        counts = self.sequence[min(self.index, len(self.sequence) - 1)]
        self.index += 1
        self.last = {"group_spike_counts": dict(counts), "source": "fake"}
        return Decision(self.raw_action, 0.0, 0.0, self.version)

    def telemetry(self):
        return self.last

    def close(self):
        self.closed = True


def counts(**values):
    result = {name: 0 for name in GROUP_ORDER}
    result.update(values)
    return result


def test_canonical_preserves_worker_action_and_records_boundary():
    base = FakeBase([counts(B=100, FORWARD=1)])
    policy = TemporalReadoutPolicy(base, "canonical")
    decision = policy.act(np.zeros(18, dtype=np.float32))
    assert decision.action == int(Action.B)
    assert decision.policy_version == base.version
    telemetry = policy.telemetry()
    assert telemetry["raw_worker_action"] == int(Action.B)
    assert telemetry["applied_action"] == int(Action.B)
    assert telemetry["readout_residual"] is None
    assert telemetry["readout_game_state_used"] is False


def test_delta_removes_stationary_between_group_bias():
    base = FakeBase([
        counts(B=100, FORWARD=10, A=5),
        counts(B=101, FORWARD=30, A=6),
    ])
    policy = TemporalReadoutPolicy(base, "delta")
    first = policy.act(np.zeros(18, dtype=np.float32))
    second = policy.act(np.zeros(18, dtype=np.float32))
    assert first.action == int(Action.NEUTRAL)
    assert second.action == int(Action.FORWARD)
    assert policy.telemetry()["readout_residual"]["FORWARD"] == 20.0


def test_ema_residual_uses_neural_history_only_and_can_select_attack():
    base = FakeBase([
        counts(B=100, A=10),
        counts(B=101, A=35),
    ])
    policy = TemporalReadoutPolicy(base, "ema-residual", ema_alpha=0.1)
    assert policy.act(np.zeros(18, dtype=np.float32)).action == int(Action.NEUTRAL)
    second = policy.act(np.zeros(18, dtype=np.float32))
    assert second.action == int(Action.A)
    telemetry = policy.telemetry()
    assert telemetry["readout_game_state_used"] is False
    assert telemetry["readout_ema_alpha"] == 0.1


def test_reset_clears_temporal_state_and_delegates():
    base = FakeBase([counts(B=100), counts(FORWARD=50)])
    policy = TemporalReadoutPolicy(base, "delta")
    policy.act(np.zeros(18, dtype=np.float32))
    policy.act(np.zeros(18, dtype=np.float32))
    policy.reset()
    assert policy.previous is None and policy.ema is None
    assert policy.telemetry() is None
    assert policy.act(np.zeros(18, dtype=np.float32)).action == int(Action.NEUTRAL)


def test_invalid_mode_and_missing_counts_fail_closed():
    base = FakeBase([counts()])
    with pytest.raises(ValueError):
        TemporalReadoutPolicy(base, "unknown")
    base.sequence = [{}]
    policy = TemporalReadoutPolicy(base, "delta")
    with pytest.raises(RuntimeError):
        policy.act(np.zeros(18, dtype=np.float32))


def test_close_delegates_to_worker_policy():
    base = FakeBase([counts()])
    policy = TemporalReadoutPolicy(base, "canonical")
    policy.close()
    assert base.closed is True
