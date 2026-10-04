"""Software contracts for terminal-credit calibration experiments."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_terminal_gain_is_calibrated_from_observed_terminal_dominance():
    # Source evidence measured from immutable Actions artifacts:
    # win run 2314: local mean step 4.7532647e-05, terminal mean step 4.7105551e-04
    # loss run 2312: local mean step 1.3318452e-04, terminal mean step 1.2864470e-03
    win_local = 4.753264715773309e-05
    win_terminal = 0.0004710555076599121
    loss_local = 0.00013318452169996942
    loss_terminal = 0.0012864470481872559
    calibrated_effective_terminal = (
        2.0 * win_local / win_terminal + 2.0 * loss_local / loss_terminal
    ) / 2.0
    assert 0.19 < calibrated_effective_terminal < 0.22
    assert abs(2.0 * 0.1 - calibrated_effective_terminal) < 0.01


def test_experiment_reproduces_main_win_and_loss_proposals():
    source = (ROOT / 'scripts/terminal_credit_gain_counterfactual.py').read_text()
    assert "PARENT_GENERATION = 49" in source
    assert "a5c2394d69eecba27c971688dcb88f7992ab872331d8d18d4d9a295d75c4b0fe" in source
    assert "TERMINAL_SIGNAL_GAIN = 0.1" in source

    assert "37194981515" in source
    assert "986465" in source and "949593" in source
    assert "e8c60365547c8e264b7c8252cf7c104f96c491168475f6427af620db001dd7e6" in source

    assert "37195556700" in source
    assert "961650" in source and "875148" in source
    assert "085d10369e4b71fd6f580b5ad3dd93f9764a01bc84a2956e9450e80094926761" in source

    assert "control_dominance['terminal_step_fraction'] < 0.85" in source
    assert "required_improved = 4" in source
    assert "advance-terminal-gain-0.1-to-confirmatory-independent-holdout" in source
    assert "'canonical_reward_changed': False" in source
    assert "'canonical_learning_changed': False" in source
    assert "'auto_promotion': False" in source


def test_terminal_gain_selection_seeds_are_new_and_separate():
    source = (ROOT / 'scripts/terminal_credit_gain_counterfactual.py').read_text()
    new_p1 = {840111, 840112, 840211, 840212, 840311, 840312}
    known = {
        800101,
        810101, 810202, 810303,
        820111, 820112, 820211, 820212, 820311, 820312,
        830111, 830112, 830211, 830212, 830311, 830312,
        986465, 961650, 1000036,
    }
    assert new_p1.isdisjoint(known)
    for seed in sorted(new_p1):
        assert str(seed) in source
    assert source.count("terminal-gain-s") == 6


def test_experiment_updater_scales_only_terminal_component():
    source = (ROOT / 'scripts/update_malecns_terminal_gain_counterfactual.py').read_text()
    assert "local_signal = float(event['damage_reward']) + float(event['potential_reward'])" in source
    assert "terminal_component = float(event['terminal_reward']) + float(event['finish_bonus'])" in source
    assert "scaled_terminal = gain * terminal_component" in source
    assert "scaled_signal = local_signal + scaled_terminal" in source
    assert "'reward_definition_changed': False" in source
    assert "'only_terminal_credit_gain_changed': True" in source
    assert "'canonical_training_eligible': False" in source


def test_terminal_gain_workflow_is_read_only_and_pinned():
    workflow = (ROOT / '.github/workflows/terminal-credit-gain-counterfactual.yml').read_text()
    assert "permissions:\n  contents: read" in workflow
    assert "contents: write" not in workflow
    assert "/dispatches" not in workflow
    assert "release upload" not in workflow
    assert "vercel" not in workflow.lower()
    assert "RUNTIME_ASSET_ID: '568215636'" in workflow
    assert "RUNTIME_SHA256: a5f03b13890dbe6b29ef5e646f885b92013610dc4f8c16b2a54b94393d8c73c4" in workflow
    assert "PARENT_ASSET_ID: '599773615'" in workflow
    assert "PARENT_ARCHIVE_SHA256: 9f2b970836d634f6de4b67b0f6b98c3bc5f9d6de539156701a6e27f88cdc3671" in workflow
    assert "--timeout-seconds 3000" in workflow
