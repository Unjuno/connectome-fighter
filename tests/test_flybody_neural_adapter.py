from __future__ import annotations

import math

import numpy as np

from connectome_fighter.flybody_neural_adapter import flybody_action, neural_fly_command


def test_neural_command_uses_real_annotations_not_game_group_labels():
    rows = [
        {"group": "A", "body_id": 10, "spikes": 20, "superclass": "vnc_motor", "soma_neuromere": "T1", "root_side": "L"},
        {"group": "FORWARD", "body_id": 11, "spikes": 8, "superclass": "vnc_motor", "soma_neuromere": "T2", "root_side": "R"},
        {"group": "C", "body_id": 12, "spikes": 6, "superclass": "descending_neuron", "root_side": "R"},
        {"group": "B", "body_id": 13, "spikes": 100, "superclass": "central"},
    ]
    command = neural_fly_command(rows, activity_scale_spikes=16)
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


def test_flybody_action_is_bounded_and_lateralized():
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
    assert action.shape == lo.shape
    assert np.all(action >= lo) and np.all(action <= hi)
    assert action[1] != action[4]
    assert action[-1] == 0.0


def test_empty_motor_activity_keeps_leg_targets_at_neutral_centers():
    names = ["coxa_T1_left", "femur_T2_right"]
    lo = [-2.0, -4.0]
    hi = [2.0, 4.0]
    command = neural_fly_command([], activity_scale_spikes=16)
    action = flybody_action(names, lo, hi, command, phase=1.2)
    assert np.allclose(action, [0.0, 0.0])
    assert command.drive == 0.0
