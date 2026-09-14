"""A new reward must have a new fingerprint and preserve the source checkpoint."""
from dataclasses import replace
import numpy as np
import pytest
from connectome_fighter.combat_checkpoint import fork_reward
from connectome_fighter.valence_plasticity import ValencePlasticityConfig,initialize_state,save_state,load_state
from connectome_fighter.combat_reward import REWARD_ID


def test_exact_weights_fork_and_source_unchanged(tmp_path):
    old=ValencePlasticityConfig();new=replace(old,reward_id=REWARD_ID)
    state=initialize_state(character='GARNET',n_candidates=4,candidate_sha256='a'*64,config=old)
    state.multipliers=np.array([1,.9,.8,.95],dtype=np.float32);state.generation=9;state.matches=9
    source=tmp_path/'source.npz';dest=tmp_path/'fork.npz';save_state(source,state,old)
    original=(source.read_bytes(),source.with_suffix('.npz.json').read_bytes())
    receipt=fork_reward(source,dest,old,new)
    assert receipt['weights_identical'] and receipt['parent_generation']==9
    assert original==(source.read_bytes(),source.with_suffix('.npz.json').read_bytes())
    result=load_state(dest,expected_character='GARNET',n_candidates=4,expected_candidate_sha256='a'*64,config=new)
    np.testing.assert_array_equal(result.multipliers,state.multipliers)
    with pytest.raises(ValueError): load_state(dest,expected_character='GARNET',n_candidates=4,expected_candidate_sha256='a'*64,config=old)
    with pytest.raises(ValueError): fork_reward(source,source,old,new)
    with pytest.raises(ValueError): fork_reward(source,tmp_path/'bad.npz',old,replace(new,learning_rate=.02))
