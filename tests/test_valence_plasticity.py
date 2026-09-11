from pathlib import Path

import numpy as np

from connectome_fighter.valence_plasticity import (
    ValencePlasticityConfig,
    apply_modulatory_signal,
    finish_match,
    initialize_state,
    load_state,
    save_state,
)


def test_signal_targets_separate_mbon_valence_channels(tmp_path: Path):
    cfg = ValencePlasticityConfig()
    state = initialize_state(character="GARNET", n_candidates=4, candidate_sha256="abc", config=cfg)
    channels = np.array([
        "avoidance_associated", "approach_associated",
        "avoidance_associated", "approach_associated",
    ])
    eligibility = np.array([10.0, 10.0, 5.0, 5.0])

    before = state.multipliers.copy()
    pos = apply_modulatory_signal(state, eligibility, +1.0, channels, cfg)
    after_pos = state.multipliers.copy()
    assert pos["target_channel"] == "avoidance_associated"
    assert np.all(after_pos[[0, 2]] < before[[0, 2]])
    assert np.all(after_pos[[1, 3]] == before[[1, 3]])
    assert pos["potentiated_edges"] == 0

    neg = apply_modulatory_signal(state, eligibility, -1.0, channels, cfg)
    after_neg = state.multipliers.copy()
    assert neg["target_channel"] == "approach_associated"
    assert np.all(after_neg[[1, 3]] < after_pos[[1, 3]])
    assert np.all(after_neg[[0, 2]] == after_pos[[0, 2]])
    assert neg["potentiated_edges"] == 0

    finish_match(state)
    assert state.generation == 1 and state.matches == 1 and state.update_events == 2

    path = tmp_path / "garnet.npz"
    meta = save_state(path, state, cfg)
    restored = load_state(
        path,
        expected_character="GARNET",
        n_candidates=4,
        expected_candidate_sha256="abc",
        config=cfg,
    )
    assert meta["reward_id"] == "R2d-v0"
    assert np.array_equal(restored.multipliers, state.multipliers)
    assert restored.generation == 1


def test_zero_signal_is_exact_noop():
    cfg = ValencePlasticityConfig()
    state = initialize_state(character="ZEN", n_candidates=2, candidate_sha256="def", config=cfg)
    before = state.multipliers.copy()
    metrics = apply_modulatory_signal(
        state,
        np.array([20.0, 20.0]),
        0.0,
        np.array(["avoidance_associated", "approach_associated"]),
        cfg,
    )
    assert np.array_equal(state.multipliers, before)
    assert state.update_events == 0
    assert metrics["changed_edges"] == 0
