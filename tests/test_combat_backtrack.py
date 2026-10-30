"""Backtracking candidate software contract, not evidence of stronger fighting."""
import json
from pathlib import Path

import numpy as np
import pytest

from connectome_fighter.combat_checkpoint import config_from_json
from connectome_fighter.valence_plasticity import initialize_state, save_state, load_state, sha256_file
from scripts.combat_candidate_backtrack import make_backtracked_checkpoint, SCHEME

ROOT=Path(__file__).resolve().parents[1]
PLASTIC=ROOT/'configs/plasticity_combat_v1.json'
CREDIT=ROOT/'configs/reward_r2f_credit_balanced_v1.json'


def source_state(tmp_path):
    cfg=config_from_json(json.loads(PLASTIC.read_text()))
    state=initialize_state(character='GARNET',n_candidates=4,
                           candidate_sha256='immutable-candidate-identity',config=cfg)
    state.multipliers[:]=np.array([1.0,0.95,0.88,0.81],dtype=np.float32)
    state.generation=49
    state.matches=49
    state.update_events=50
    parent=tmp_path/'parent/GARNET.npz'
    proposed=tmp_path/'proposed/GARNET.npz'
    save_state(parent,state,cfg)
    state.multipliers[:]=np.array([0.98,0.91,0.82,0.80],dtype=np.float32)
    state.generation=50
    state.matches=50
    state.update_events=51
    meta=save_state(proposed,state,cfg)
    meta['learning_credit_id']='R2f-credit-balanced-v1'
    meta['learning_credit_sha256']=sha256_file(CREDIT)
    meta['external_evaluation_reward_id']='R2e-combat-v1'
    proposed.with_suffix('.npz.json').write_text(json.dumps(meta))
    return parent,proposed,cfg


def test_bounded_production_candidate_is_halfway_to_no_update_not_potentiated(tmp_path):
    parent,proposal,cfg=source_state(tmp_path)
    out=tmp_path/'backtrack/GARNET.npz'
    frozen_parent=(sha256_file(parent),sha256_file(parent.with_suffix('.npz.json')))
    frozen_proposal=(sha256_file(proposal),sha256_file(proposal.with_suffix('.npz.json')))
    result=make_backtracked_checkpoint(parent,proposal,out,PLASTIC,CREDIT)
    assert result['kind']==SCHEME
    assert result['step_scale']==0.25
    assert result['potentiated_edges']==0 and result['updated_edges']==4
    p=load_state(parent,expected_character='GARNET',n_candidates=4,
                 expected_candidate_sha256='immutable-candidate-identity',config=cfg)
    q=load_state(proposal,expected_character='GARNET',n_candidates=4,
                 expected_candidate_sha256='immutable-candidate-identity',config=cfg)
    b=load_state(out,expected_character='GARNET',n_candidates=4,
                 expected_candidate_sha256='immutable-candidate-identity',config=cfg)
    expected=(p.multipliers.astype(np.float64)+0.25*(
              q.multipliers.astype(np.float64)-p.multipliers.astype(np.float64))).astype(np.float32)
    np.testing.assert_array_equal(b.multipliers,expected)
    assert (b.generation,b.matches,b.update_events)==(50,50,51)
    assert np.all(b.multipliers<=p.multipliers)
    assert np.all(b.multipliers>=q.multipliers)
    assert sha256_file(out)==result['backtracked_sha256']
    meta=json.loads(out.with_suffix('.npz.json').read_text())
    assert meta['proposal_step_scheme']==SCHEME
    assert meta['proposal_step_scale']==0.25
    assert meta['external_evaluation_reward_id']=='R2e-combat-v1'
    assert meta['learning_credit_sha256']==sha256_file(CREDIT)
    assert frozen_parent==(sha256_file(parent),sha256_file(parent.with_suffix('.npz.json')))
    assert frozen_proposal==(sha256_file(proposal),sha256_file(proposal.with_suffix('.npz.json')))
    with pytest.raises(ValueError,match='overwrite'):
        make_backtracked_checkpoint(parent,proposal,out,PLASTIC,CREDIT)


def test_refuse_potentiation_and_identity_tampering(tmp_path):
    parent,proposal,cfg=source_state(tmp_path)
    q=load_state(proposal,expected_character='GARNET',n_candidates=4,
                 expected_candidate_sha256='immutable-candidate-identity',config=cfg)
    q.multipliers[0]=1.0
    # An updated weight above the parent must fail closed.
    p=load_state(parent,expected_character='GARNET',n_candidates=4,
                 expected_candidate_sha256='immutable-candidate-identity',config=cfg)
    p.multipliers[0]=0.90
    save_state(parent,p,cfg)
    with pytest.raises(ValueError,match='depression-only'):
        make_backtracked_checkpoint(parent,proposal,tmp_path/'bad/GARNET.npz',PLASTIC,CREDIT)
    # Restore and tamper the credit record only.
    parent.unlink()
    parent.with_suffix('.npz.json').unlink()
    parent,proposal,cfg=source_state(tmp_path)
    meta=json.loads(proposal.with_suffix('.npz.json').read_text())
    meta['learning_credit_sha256']='f'*64
    proposal.with_suffix('.npz.json').write_text(json.dumps(meta))
    with pytest.raises(ValueError,match='credit'):
        make_backtracked_checkpoint(parent,proposal,tmp_path/'tampered/GARNET.npz',PLASTIC,CREDIT)


def test_integration_uses_frozen_r2e_validation_for_full_and_reduced_proposal():
    source=(ROOT/'scripts/combat_training_run.py').read_text()
    assert "alt_gate=paired_evaluation_suite_gate(alt_cases,reward_config)" in source
    assert "gate=paired_evaluation_suite_gate(gate_cases,reward_config)" in source
    assert "if alt_gate['accepted_update']:" in source
    assert "if not gate['accepted_update']:" in source
    assert "meta['proposal_step_scale']==0.25" in source
    assert "'auto_promotion':False" in source
