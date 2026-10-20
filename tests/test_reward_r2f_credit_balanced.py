"""R2f contract tests: software behavior only, NOT evidence of fighting strength."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from connectome_fighter import combat_reward as r2e
from connectome_fighter import combat_reward_r2f as r2f
from connectome_fighter.combat_checkpoint import config_from_json
from connectome_fighter.combat_reward_r2f_checkpoint import fork_r2e_to_r2f
from connectome_fighter.valence_plasticity import (
    initialize_state, load_state, save_state, sha256_file,
)

ROOT = Path(__file__).resolve().parents[1]
R2F = json.loads((ROOT / "configs/reward_r2f_credit_balanced_v1.json").read_text())
R2E = json.loads((ROOT / "configs/reward_r2e_combat_v1.json").read_text())


def trace(final=(400, 400), elapsed=3600, positions=(500, 400, 300)):
    return {
        "kind": "round", "terminated": True, "truncated": False,
        "trainable": True, "player_index": 0, "remaining_hps": list(final),
        "elapsed_frame": elapsed,
        "transitions": [
            {
                "frame": f, "policy_version": "frozen",
                "brain": {"trace_decision_index": i},
                "display": {"p1": {"hp": 400, "x": 0}, "p2": {"hp": 400, "x": d}},
            }
            for i, (f, d) in enumerate(zip((1, 61, 121), positions))
        ],
    }


def test_configuration_is_versioned_and_canonical_objective_is_frozen():
    r2f.validate_config(R2F)
    r2e.validate_config(R2E)
    assert R2F["base_reward"] == R2E
    assert R2F["automatic_promotion"] is False
    for part, val in (
        ("terminal_win_loss_gain", 0.25),
        ("no_damage_draw_credit", -0.01),
        ("terminal_ko_bonus_gain", float("nan")),
    ):
        bad = copy.deepcopy(R2F)
        bad["training_credit"][part] = val
        with pytest.raises(ValueError):
            r2f.validate_config(bad)
    bad = copy.deepcopy(R2F)
    bad["evaluation_reward_id"] = "R2f-credit-balanced-v1"
    with pytest.raises(ValueError):
        r2f.validate_config(bad)


@pytest.mark.parametrize(
    "final,expected",
    [
        ((390, 350), 1.0),   # winning full round
        ((350, 390), -1.0),  # losing full round
        ((400, 400), 0.0),  # no damage, no damaging depression credit
        ((350, 350), 0.0),  # damaging draw
    ],
)
def test_terminal_credit_without_changing_local_signal(final, expected):
    row = trace(final=final)
    canonical = r2e.reward_sequence(row, 0, R2E)
    modified = r2f.reward_sequence(row, 0, R2F)
    assert modified[-1]["terminal_reward"] == expected
    assert canonical[-1]["signal"] == modified[-1]["canonical_r2e_signal"]
    assert all(a["damage_reward"] == b["damage_reward"] and
               a["potential_reward"] == b["potential_reward"]
               for a, b in zip(canonical, modified))
    assert all(b["learning_reward_id"] == r2f.REWARD_ID for b in modified)
    assert sum(x["terminal_reward"] != 0 for x in modified[:-1]) == 0
    assert canonical[-1]["terminal_reward"] == (
        2.0 if expected == 1.0 else -2.0 if expected == -1.0
        else (-0.25 if final == (400,400) else -0.05)
    )


def test_no_damage_stalemate_no_terminal_depression_but_approach_signal_remains():
    e = r2f.reward_sequence(trace(), 0, R2F)
    assert e[-1]["terminal_reward"] == 0
    assert sum(x["signal"] for x in e) == pytest.approx(0.05 * 320 / 960)
    assert sum(x["signal"] < 0 for x in e) == 0


def test_early_ko_bonus_is_scaled_but_unchanged_evaluation_utility():
    row = trace(final=(350, 0), elapsed=1800)
    original = r2e.reward_sequence(row, 0, R2E)
    balanced = r2f.reward_sequence(row, 0, R2F)
    assert original[-1]["finish_bonus"] == pytest.approx(0.125)
    assert balanced[-1]["finish_bonus"] == pytest.approx(0.0625)
    assert balanced[-1]["terminal_reward"] == 1.0
    metrics = dict(p1_hp=350, p2_hp=0, damage_dealt_hp=400, damage_taken_hp=50,
                   elapsed_frame=1800)
    assert r2f.evaluation_utility(metrics,R2F) == r2e.paired_evaluation_utility(metrics,R2E)
    assert r2f.evaluation_utility(metrics,R2F) > 2.0


def test_no_action_label_reward():
    t1 = trace()
    t2 = copy.deepcopy(t1)
    for e in t2["transitions"]:
        e["action"] = "B"
        e["requested_keys"] = {"B": True}
    assert r2f.reward_sequence(t1,0,R2F) == r2f.reward_sequence(t2,0,R2F)


def test_invalid_rounds_fail_closed():
    for key, value in [
        ("truncated", True), ("terminated", False), ("trainable", False),
        ("player_index", 1), ("elapsed_frame", 3400),
    ]:
        t = trace()
        t[key] = value
        with pytest.raises(ValueError):
            r2f.reward_sequence(t, 0, R2F)
    t = trace()
    t["trainable"] = False
    assert r2f.reward_sequence(t,0,R2F,require_trainable=False)


def test_component_audit_rejects_tampering_and_bad_terminal_location():
    canonical = r2e.reward_sequence(trace(),0,R2E)
    bad = copy.deepcopy(canonical)
    bad[-1]["signal"] += 0.1
    with pytest.raises(ValueError):
        r2f.rebalance_events(bad,R2F)
    bad = copy.deepcopy(canonical)
    bad[0]["terminal_reward"] = -0.25
    with pytest.raises(ValueError):
        r2f.rebalance_events(bad,R2F)
    bad = copy.deepcopy(canonical)
    bad[-1]["last"] = False
    with pytest.raises(ValueError):
        r2f.rebalance_events(bad,R2F)


def test_existing_updater_explicit_r2f_dispatch():
    from scripts.update_malecns_valence_plasticity import reward_sequence as routed
    assert routed(trace(),0,R2F) == r2f.reward_sequence(trace(),0,R2F)
    assert routed(trace(),0,R2E) == r2e.reward_sequence(trace(),0,R2E)


def test_checkpoint_fork_keeps_weights_and_generation_and_never_writes_parent(tmp_path):
    old = config_from_json(json.loads((ROOT/"configs/plasticity_combat_v1.json").read_text()))
    new = config_from_json(json.loads((ROOT/"configs/plasticity_r2f_credit_balanced_v1.json").read_text()))
    source=tmp_path/"canonical"/"GARNET.npz"
    dest=tmp_path/"research"/"GARNET.npz"
    state=initialize_state(character="GARNET",n_candidates=3,
                           candidate_sha256="immutable-candidates",config=old)
    state.multipliers[:]=np.array([0.83,0.91,0.97],dtype=np.float32)
    state.generation=49
    state.matches=49
    state.update_events=8
    save_state(source,state,old)
    sha0=sha256_file(source)
    meta0=sha256_file(source.with_suffix(".npz.json"))
    receipt=fork_r2e_to_r2f(source,dest,old,new)
    forked=load_state(dest,expected_character="GARNET",n_candidates=3,
                      expected_candidate_sha256="immutable-candidates",config=new)
    assert receipt["weights_identical"] and not receipt["automatic_promotion"]
    assert np.array_equal(forked.multipliers,state.multipliers)
    assert (forked.generation,forked.matches,forked.update_events)==(49,49,8)
    assert sha256_file(source)==sha0 and sha256_file(source.with_suffix(".npz.json"))==meta0
    assert json.loads(dest.with_suffix(".npz.fork.json").read_text())["source_checkpoint_sha256"]==sha0
    with pytest.raises(ValueError):
        fork_r2e_to_r2f(source,dest,old,new)
    with pytest.raises(ValueError):
        fork_r2e_to_r2f(source,source,old,new)
    with pytest.raises(ValueError):
        fork_r2e_to_r2f(source,tmp_path/"wrong.npz",new,old)
