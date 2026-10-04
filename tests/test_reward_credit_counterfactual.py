"""Software contracts for the Gen49 reward-credit counterfactual lane."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r2f_changes_only_no_damage_terminal_penalty_and_reference():
    r2e = json.loads((ROOT / 'configs/reward_r2e_combat_v1.json').read_text())
    r2f = json.loads((ROOT / 'configs/reward_r2f_nodamage_neutral_v0.json').read_text())
    p2e = json.loads((ROOT / 'configs/plasticity_combat_v1.json').read_text())
    p2f = json.loads((ROOT / 'configs/plasticity_combat_r2f_v0.json').read_text())

    for row in (r2e, r2f):
        row.pop('status', None)
        row.pop('interpretation_boundary', None)
    r2e['id'] = r2f['id']
    r2e['terminal']['no_damage_draw_penalty'] = 0.0
    assert r2e == r2f

    ignored = {'status', 'reward_config', 'interpretation_boundary'}
    assert {k: v for k, v in p2e.items() if k not in ignored} == {
        k: v for k, v in p2f.items() if k not in ignored
    }
    assert p2f['reward_config'] == 'R2f-combat-nodamage-neutral-v0'


def test_counterfactual_is_pinned_and_cannot_publish():
    source = (ROOT / 'scripts/reward_credit_counterfactual.py').read_text()
    assert "PARENT_GENERATION = 49" in source
    assert "a5c2394d69eecba27c971688dcb88f7992ab872331d8d18d4d9a295d75c4b0fe" in source
    assert "bc602d637758c28c107f029e55d7732524a9ebe926ed0b73ad8f7aa687c97027" in source
    assert "SOURCE_RUN_ID = 37194195086" in source
    assert "SOURCE_RUN_NUMBER = 2310" in source
    assert "'opponent': 'NEZ', 'seed_p1': 1000036, 'seed_p2': 990306" in source
    assert "'auto_promotion': False" in source
    assert "'canonical_learning_changed': False" in source
    assert "advance-r2f-to-confirmatory-independent-holdout" in source
    assert "REWARD_SELECTION_SUITE" in source
    for seed in (830111, 830112, 830211, 830212, 830311, 830312):
        assert str(seed) in source
    assert "reward_selection_common_objective" in source
    assert "required_improved = 4" in source
    assert "previously unused seeds" in source


def test_reward_selection_seeds_do_not_reuse_known_training_validation_or_holdout_sets():
    source = (ROOT / 'scripts/reward_credit_counterfactual.py').read_text()
    new_seeds = {830111, 830112, 830211, 830212, 830311, 830312}
    known = {
        800101, 20202,
        810101, 31001, 810202, 31002, 810303, 31003,
        820111, 32011, 820112, 32012,
        820211, 32021, 820212, 32022,
        820311, 32031, 820312, 32032,
        1000036, 990306,
    }
    assert new_seeds.isdisjoint(known)
    assert source.count("reward-select-s") == 6
