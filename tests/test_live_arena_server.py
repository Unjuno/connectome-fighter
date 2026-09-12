from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_live_arena_server.py"
    spec = importlib.util.spec_from_file_location("run_live_arena_server", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_brain_sample_preserves_action_group_spike_competition_and_causal_edges():
    module = load_module()
    event = {
        "frame": 180,
        "brain": {
            "trace_decision_index": 3,
            "biological_time_start_ms": 40.0,
            "biological_time_end_ms": 60.0,
            "total_spikes": 9245,
            "unique_spike_bodies": 812,
            "group_spike_counts": {
                "FORWARD": 2,
                "BACKWARD": 8,
                "UP": 1,
                "DOWN": 3,
                "A": 0,
                "B": 17,
                "C": 4,
            },
            "top_spike_bodies": [[123, 11], [456, 7]],
            "sensory_drive_top": [[111, 150.0], [222, 75.0]],
            "output_contributions_top": [["B", 333, 9.0], ["BACKWARD", 444, 6.0]],
            "membrane_summary": {"v_mean_mV": -50.2, "g_mean_mV": 1.4},
        },
    }

    sample = module.ArenaState._brain_sample(event)

    assert sample["decision_index"] == 3
    assert sample["biological_time_start_ms"] == 40.0
    assert sample["biological_time_end_ms"] == 60.0
    assert sample["total_spikes"] == 9245
    assert sample["unique_bodies"] == 812
    assert sample["group_spike_counts"]["B"] == 17
    assert sample["group_spike_counts"]["BACKWARD"] == 8
    assert sample["sensory_drive"] == [
        {"body_id": 111, "rate_hz": 150.0},
        {"body_id": 222, "rate_hz": 75.0},
    ]
    assert sample["output_contributions"] == [
        {"group": "B", "body_id": 333, "spikes": 9.0},
        {"group": "BACKWARD", "body_id": 444, "spikes": 6.0},
    ]
    assert sample["membrane_summary"] == {"v_mean_mV": -50.2, "g_mean_mV": 1.4}
    assert sample["top_bodies"] == [
        {"body_id": 123, "spikes": 11},
        {"body_id": 456, "spikes": 7},
    ]


def test_brain_sample_rejects_malformed_spectator_values():
    module = load_module()
    event = {
        "frame": 60,
        "brain": {
            "group_spike_counts": {"B": 5, "bad": "not-a-number"},
            "sensory_drive_top": [[123, 90.0], ["bad"]],
            "output_contributions_top": [["B", 456, 4.0], ["bad"]],
            "membrane_summary": {"v_mean_mV": -51.0, "bad": "x"},
        },
    }

    sample = module.ArenaState._brain_sample(event)
    assert sample["group_spike_counts"] == {"B": 5}
    assert sample["sensory_drive"] == [{"body_id": 123, "rate_hz": 90.0}]
    assert sample["output_contributions"] == [{"group": "B", "body_id": 456, "spikes": 4.0}]
    assert sample["membrane_summary"] == {"v_mean_mV": -51.0}


def test_live_payload_schema_three_exposes_round_reuse():
    module = load_module()
    state = module.ArenaState(session_id="s", p1="GARNET", p2="ZEN", max_hp=400, rounds_per_session=6)
    payload = state.payload()
    assert payload["schema_version"] == 3
    assert payload["rounds_per_session"] == 6
    assert payload["learning_enabled"] is False
    assert payload["policy_pixel_access"] is False


def test_shared_public_broadcast_defaults_to_six_rounds(monkeypatch):
    module = load_module()
    monkeypatch.setenv("CONNECTOME_PUBLIC_BROADCAST", "true")
    monkeypatch.delenv("CONNECTOME_ROUNDS_PER_SESSION", raising=False)
    assert module.rounds_per_session_from_env() == 6


def test_non_public_session_defaults_to_one_round(monkeypatch):
    module = load_module()
    monkeypatch.delenv("CONNECTOME_PUBLIC_BROADCAST", raising=False)
    monkeypatch.delenv("CONNECTOME_ROUNDS_PER_SESSION", raising=False)
    assert module.rounds_per_session_from_env() == 1


def test_rounds_per_session_override_is_bounded(monkeypatch):
    module = load_module()
    monkeypatch.setenv("CONNECTOME_PUBLIC_BROADCAST", "true")
    monkeypatch.setenv("CONNECTOME_ROUNDS_PER_SESSION", "9")
    assert module.rounds_per_session_from_env() == 9
    monkeypatch.setenv("CONNECTOME_ROUNDS_PER_SESSION", "0")
    with pytest.raises(ValueError):
        module.rounds_per_session_from_env()
    monkeypatch.setenv("CONNECTOME_ROUNDS_PER_SESSION", "61")
    with pytest.raises(ValueError):
        module.rounds_per_session_from_env()
