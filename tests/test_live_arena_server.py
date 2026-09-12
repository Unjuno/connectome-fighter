from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_live_arena_server.py"
    spec = importlib.util.spec_from_file_location("run_live_arena_server", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_brain_sample_preserves_action_group_spike_competition():
    module = load_module()
    event = {
        "frame": 180,
        "brain": {
            "trace_decision_index": 3,
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
        },
    }

    sample = module.ArenaState._brain_sample(event)

    assert sample["decision_index"] == 3
    assert sample["total_spikes"] == 9245
    assert sample["unique_bodies"] == 812
    assert sample["group_spike_counts"]["B"] == 17
    assert sample["group_spike_counts"]["BACKWARD"] == 8
    assert sample["top_bodies"] == [
        {"body_id": 123, "spikes": 11},
        {"body_id": 456, "spikes": 7},
    ]


def test_brain_sample_rejects_non_numeric_group_values():
    module = load_module()
    event = {
        "frame": 60,
        "brain": {
            "group_spike_counts": {"B": 5, "bad": "not-a-number"},
        },
    }

    sample = module.ArenaState._brain_sample(event)
    assert sample["group_spike_counts"] == {"B": 5}
