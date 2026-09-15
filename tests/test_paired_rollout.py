"""Engineering tests only: artificial arrays and publication envelopes."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from connectome_fighter.paired_rollout import *


def parent(tmp_path):
    p=tmp_path/'parent.npz'
    values=np.full(8,.95,dtype=np.float32)
    np.savez_compressed(p,multipliers=values)
    return Parent(values,11,{'cycle_index':0,'accepted_update_count':0,'origin_generation':11,
                            'origin_state_sha256':file_hash(p),'next_phase':'curriculum','mastery_streak':0,
                            'substrate':{k:'c'*64 for k in SUBSTRATE_KEYS}},p)


def test_no_update_preserves_weights_generation_but_advances_cycle(tmp_path):
    par=parent(tmp_path);membership=np.arange(8,dtype=np.int64)
    out=tmp_path/'resume/candidate'
    m=save_checkpoint(out,par,membership,par.multipliers,False,'a'*64,[],'curriculum')
    assert m['cycle_index']==1 and m['generation']==11 and m['accepted_update_count']==0
    assert m['weights_sha256']==m['parent_weights_sha256']
    loaded=load_parent(tmp_path/'resume','a'*64,membership,None)
    assert np.array_equal(loaded.multipliers,par.multipliers)
    m2=save_checkpoint(tmp_path/'second/candidate',loaded,membership,loaded.multipliers,False,'a'*64,[],'curriculum')
    assert m2['cycle_index']==2 and m2['generation']==11
    assert m['seed_plan']!=m2['seed_plan']


def test_accepted_update_increments_only_on_changed_arrays(tmp_path):
    par=parent(tmp_path);values=par.multipliers.copy();values[0]-=.01
    m=save_checkpoint(tmp_path/'new',par,np.arange(8),values,True,'a'*64,[],'curriculum')
    assert m['generation']==12 and m['accepted_update_count']==1 and m['weights_changed']


@pytest.mark.parametrize('claimed,change',[(True,False),(False,True)])
def test_claim_must_match_weights(tmp_path,claimed,change):
    par=parent(tmp_path);values=par.multipliers.copy()
    if change:values[0]-=.01
    with pytest.raises(ValueError):save_checkpoint(tmp_path/'new',par,np.arange(8),values,claimed,'a'*64,[],'curriculum')


@pytest.mark.parametrize('mutation',['hash','weights','membership','protocol','count','phase','incomplete'])
def test_corrupt_resume_fails_closed(tmp_path,mutation):
    par=parent(tmp_path);out=tmp_path/'resume/candidate';membership=np.arange(8)
    m=save_checkpoint(out,par,membership,par.multipliers,False,'a'*64,[],'curriculum')
    if mutation=='hash':m['state_file_sha256']='0'*64
    if mutation=='weights':m['weights_sha256']='0'*64
    if mutation=='membership':membership=membership[::-1]
    if mutation=='protocol':m['protocol_sha256']='0'*64
    if mutation=='count':m['accepted_update_count']=2
    if mutation=='phase':m['next_phase']='unknown'
    write_json(out/'search-state.json',m)
    if mutation=='incomplete':(out/'search-state.json').unlink()
    with pytest.raises(ValueError):load_parent(tmp_path/'resume','a'*64,membership,None)


@pytest.mark.parametrize('bad',[0,-1,True,1.0,1_000_001])
def test_bad_cycle_rejected(bad):
    with pytest.raises(ValueError):seeds(bad)


def test_seed_roles_and_cycles_disjoint():
    values=[]
    for cycle in range(1,501):
        s=seeds(cycle);values += [s['direction'],s['training'],s['selection'],*s['validation']]
    assert len(set(values))==len(values)
    assert 800101 not in values


def test_three_validated_curriculum_cycles_not_generation_count_graduate(tmp_path):
    par=parent(tmp_path);membership=np.arange(8)
    for cycle in range(1,4):
        v=par.multipliers.copy();v[0]-=.001
        val=[{'seed':s,'candidate':{'damage_dealt_hp':40}} for s in seeds(cycle)['validation']]
        d=tmp_path/f'c{cycle}'/'candidate'
        m=save_checkpoint(d,par,membership,v,True,'a'*64,val,'curriculum')
        assert m['next_phase']==('combat' if cycle==3 else 'curriculum')
        par=load_parent(d.parent,'a'*64,membership,None)
    assert m['mastery_streak']==3


def test_mastery_does_not_use_training_seed(tmp_path):
    par=parent(tmp_path);v=par.multipliers.copy();v[0]-=.001
    val=[{'seed':seeds(1)['training'],'candidate':{'damage_dealt_hp':400}}]*2
    m=save_checkpoint(tmp_path/'new',par,np.arange(8),v,True,'a'*64,val,'curriculum')
    assert m['mastery_streak']==0


def view(cycle=1,updates=0,before='a'*64,after='a'*64):
    run=f'https://github.com/Unjuno/connectome-fighter/actions/runs/{cycle}'
    ev={'status':'COMPLETED','candidate_only':True,'auto_promotion':False,'policy_pixel_access':False,
        'source_training_run_url':run,'video':{'sha256':'f'*64},'evaluation':{'fixed':True}}
    return {'schema_version':1,'rollout':ROLLOUT,'protocol_sha256':PROTOCOL_SHA256,'ready':True,
            'status':'paired-evaluation-ready','cycle_index':cycle,'accepted_update_count':updates,
            'source_run_url':run,'parent_view_sha256':None,
            'previous':dict(ev,state_sha256=before,comparison_phase='before'),
            'latest':dict(ev,state_sha256=after,comparison_phase='after')}


def test_initial_then_same_weights_next_cycle_and_retry():
    a=view();assert publication_guard(None,a);assert not publication_guard(a,a)
    b=view(2);b['parent_view_sha256']=digest(a)
    assert publication_guard(a,b)


@pytest.mark.parametrize('mutation',['stale','skipped','fork','counter','run','phase','protocol','readonly','hash'])
def test_publication_rejects_incoherent_or_stale_cycle(mutation):
    a=view();b=view(2);b['parent_view_sha256']=digest(a)
    if mutation=='stale':b['cycle_index']=1
    if mutation=='skipped':b['cycle_index']=3
    if mutation=='fork':b['previous']['state_sha256']='b'*64
    if mutation=='counter':b['accepted_update_count']=1
    if mutation=='run':b['latest']['source_training_run_url']='wrong'
    if mutation=='phase':b['latest']['comparison_phase']='before'
    if mutation=='protocol':b['latest']['evaluation']={'fixed':False}
    if mutation=='readonly':b['latest']['auto_promotion']=True
    if mutation=='hash':b['latest']['state_sha256']='x'
    with pytest.raises(ValueError):publication_guard(a,b)


@pytest.mark.parametrize('array',[np.array([np.nan]),np.array([np.inf]),np.array([.7]),np.array([1.01]),np.array([])])
def test_invalid_effective_weights_rejected(array):
    with pytest.raises(ValueError):weights_hash(array)
