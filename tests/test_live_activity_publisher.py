from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_live_activity_publisher.py"
    spec = importlib.util.spec_from_file_location("run_live_activity_publisher", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compact_brain_preserves_real_body_annotations_and_region_loads():
    module = load_module()
    event = {
        "kind": "decision",
        "side": 1,
        "character": "GARNET",
        "round_id": 2,
        "frame": 180,
        "brain": {
            "trace_decision_index": 3,
            "top_spike_bodies_annotated": [
                {"body_id": 10, "spikes": 8, "soma_neuromere": "ANm", "superclass": "descending", "type": "foo"},
                {"body_id": 11, "spikes": 5, "soma_neuromere": "ANm", "superclass": "descending", "type": "bar"},
                {"body_id": 12, "spikes": 4, "soma_neuromere": "T1", "superclass": "motor", "type": "baz"},
            ],
            "sensory_drive_top_annotated": [
                {"body_id": 20, "rate_hz": 150.0, "soma_neuromere": "AMMC"},
            ],
            "output_contributions_top_annotated": [
                {"group": "B", "body_id": 30, "spikes": 9.0, "soma_neuromere": "T1"},
            ],
        },
    }

    row = module.compact_brain(event)
    assert row["decision_index"] == 3
    assert row["round"] == 2 and row["frame"] == 180
    assert row["top_bodies"][0]["body_id"] == 10
    assert row["sensory_drive"][0]["rate_hz"] == 150.0
    assert row["motor_contributors"][0]["group"] == "B"
    assert row["neuromeres"] == [
        {"name": "ANm", "value": 13.0},
        {"name": "T1", "value": 4.0},
    ]
    assert row["superclasses"][0] == {"name": "descending", "value": 13.0}
