from __future__ import annotations

import numpy as np

from connectome_fighter.contracts import Action, Decision, Observation
from connectome_fighter.trajectory import RoundLedger


def test_decision_observer_is_side_channel_only():
    durable = []
    live = []
    ledger = RoundLedger(durable.append, trainable=False, decision_sink=live.append)
    ledger.begin("m1", 1, True, "opponent-v1")
    obs = Observation(np.zeros(18, dtype=np.float32), round_id=1, frame=10, facing_right=True)
    choice = Decision(action=Action.B, log_prob=0.0, value=0.0, policy_version="p1-v1")
    brain = {"total_spikes": 12, "unique_spike_bodies": 7, "trace_decision_index": 0}
    display = {"frame": 10, "p1": {"hp": 400, "x": 100}, "p2": {"hp": 400, "x": 700}}

    ledger.append(obs, choice, brain=brain, display=display)

    assert durable == []
    assert len(live) == 1
    event = live[0]
    assert event["kind"] == "decision"
    assert event["player_index"] == 0
    assert event["action"] == int(Action.B)
    assert event["action_name"] == "B"
    assert event["brain"] == brain
    assert event["display"] == display
    assert ledger.records[0]["action"] == int(Action.B)


def test_decision_observer_failure_does_not_change_canonical_trace():
    durable = []

    def broken(_event):
        raise RuntimeError("spectator unavailable")

    ledger = RoundLedger(durable.append, trainable=False, decision_sink=broken)
    ledger.begin("m2", 2, False, "opponent-v2")
    obs = Observation(np.zeros(18, dtype=np.float32), round_id=2, frame=20, facing_right=False)
    choice = Decision(action=Action.FORWARD, log_prob=0.0, value=0.0, policy_version="p2-v1")

    ledger.append(obs, choice)
    assert ledger.decision_sink_errors == 1
    assert ledger.records[0]["action"] == int(Action.FORWARD)

    assert ledger.finish("m2", 2, False, [350, 300], 30)
    assert len(durable) == 1
    assert durable[0]["outcome_reward"] == -1.0
    assert durable[0]["transitions"][0]["action"] == int(Action.FORWARD)
