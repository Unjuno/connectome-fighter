from __future__ import annotations

import math

import numpy as np

from connectome_fighter.flybody_neural_adapter import ADAPTER_ID, flybody_action, neural_fly_command


def test_neural_command_uses_real_annotations_not_game_group_labels():
    rows = [
        {"group": "A", "body_id": 10, "spikes": 20, "superclass": "vnc_motor", "soma_neuromere": "T1", "root_side": "L"},
        {"group": "FORWARD", "body_id": 11, "spikes": 8, "superclass": "vnc_motor", "soma_neuromere": "T2", "root_side": "R"},
        {"group": "C", "body_id": 12, "spikes": 6, "superclass": "descending_neuron", "root_side": "R"},
        {"group": "B", "body_id": 13, "spikes": 100, "superclass": "central"},
    ]
    command = neural_fly_command(rows, activity_scale_spikes=16)
    assert ADAPTER_ID == "malecns-annotated-motor-to-flybody-tripod-v2"
    assert command.to_json()["adapter"] == ADAPTER_ID
    assert command.drive > 0
    assert command.t1_drive > command.t2_drive
    assert command.right_drive > 0
    assert command.left_drive > 0
    assert command.descending_drive > 0
    assert command.source_body_ids == (10, 11, 12)
    assert 13 not in command.source_body_ids
    # Changing only the artificial FightingICE group labels cannot change the command.
    changed = [dict(row, group="DOWN") for row in rows]
    assert neural_fly_command(changed, activity_scale_spikes=16) == command


def test_flybody_action_is_bounded_lateralized_and_phase_driven():
    names = [
        "adhere_claw_T1_left", "coxa_T1_left", "femur_T1_left",
        "adhere_claw_T1_right", "coxa_T1_right", "femur_T1_right",
        "head_yaw",
    ]
    lo = np.array([0, -1, -1, 0, -1, -1, -0.5], dtype=float)
    hi = np.array([1, 1, 1, 1, 1, 1, 0.5], dtype=float)
    command = neural_fly_command([
        {"body_id": 20, "spikes": 24, "superclass": "vnc_motor", "soma_neuromere": "T1", "root_side": "L"},
        {"body_id": 21, "spikes": 2, "superclass": "vnc_motor", "soma_neuromere": "T1", "root_side": "R"},
    ], activity_scale_spikes=8)
    action = flybody_action(names, lo, hi, command, phase=math.pi / 2)
    later = flybody_action(names, lo, hi, command, phase=math.pi)
    assert action.shape == lo.shape
    assert np.all(action >= lo) and np.all(action <= hi)
    assert action[1] != action[4]
    assert not np.allclose(action, later)
    assert action[-1] == 0.0
    assert later[-1] == 0.0


def test_empty_motor_activity_keeps_leg_targets_neutral_adhesion_off_and_phase_invariant():
    names = ["adhere_claw_T1_left", "coxa_T1_left", "femur_T2_right"]
    lo = [0.0, -2.0, -4.0]
    hi = [1.0, 2.0, 4.0]
    command = neural_fly_command([], activity_scale_spikes=16)
    first = flybody_action(names, lo, hi, command, phase=0.2)
    later = flybody_action(names, lo, hi, command, phase=4.7)
    assert np.allclose(first, [0.0, 0.0, 0.0])
    assert np.allclose(later, first)
    assert command.drive == 0.0
