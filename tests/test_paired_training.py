"""Engineering tests for persistence, reward identity and publication guards."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from connectome_fighter.paired_training import (
    CONFIG, EXPERIMENT, cycle_seeds, digest, weights_sha, save_search, load_search, confirmation_pass,
)
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('paired_release',ROOT/'scripts/paired_training_release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)


def state(tmp_path,changed=False):
    origin=np.full(16,.95,dtype=np.float32);groups=np.arange(16)%8;theta=np.zeros(8)
    if changed:theta[0]=-.01
    parent={'weights_sha256':weights_sha(origin),'cycle':0}
    path=tmp_path/'search-state.npz'
    meta=save_search(path,origin=origin,theta=theta,membership=groups,parent=parent,
        runtime_identity={'interface':'fixed'},candidate_sha='a'*64,completed_games=8,accepted=changed,
        cycle=1,seed_parent={'generation':11,'reward_id':'R2e-combat-v1'})
    return path,meta,origin,theta,groups


@pytest.mark.parametrize('changed',[False,True])
def test_persistent_state_roundtrip(tmp_path,changed):
    p,m,o,t,g=state(tmp_path,changed)
    x,y=load_search(p,m,'a'*64,g,{'interface':'fixed'})
    assert np.array_equal(x,o) and np.array_equal(y,t)
    assert m['accepted_updates']==int(changed)


def test_zero_update_resume_advances_cycles_only(tmp_path):
    p,m,o,t,g=state(tmp_path)
    n=save_search(tmp_path/'second.npz',origin=o,theta=t,membership=g,parent=m,
        runtime_identity={'interface':'fixed'},candidate_sha='a'*64,completed_games=8,accepted=False,cycle=2,seed_parent=m['seed_parent'])
    assert n['cycle']==2 and n['accepted_updates']==0 and n['total_completed_games']==16
    assert n['weights_sha256']==m['weights_sha256'] and n['weights_changed'] is False


@pytest.mark.parametrize('key,value',[
    ('experiment','other'),('config_sha256','0'*64),('candidate_sha256','b'*64),
    ('runtime_identity',{'interface':'changed'}),('candidate_only',False),('auto_promotion',True),
    ('production_compatible',True),('cycle',-1),('accepted_updates',3),('state_file_sha256','0'*64),
    ('weights_sha256','0'*64),('total_completed_games',-2)])
def test_resume_fails_closed(tmp_path,key,value):
    p,m,o,t,g=state(tmp_path);m[key]=value
    with pytest.raises(ValueError):load_search(p,m,'a'*64,g,{'interface':'fixed'})


def test_grouping_cannot_change_on_resume(tmp_path):
    p,m,o,t,g=state(tmp_path)
    with pytest.raises(ValueError):load_search(p,m,'a'*64,g[::-1],{'interface':'fixed'})


def test_counter_does_not_invent_update(tmp_path):
    p,m,o,t,g=state(tmp_path)
    with pytest.raises(ValueError):save_search(tmp_path/'bad.npz',origin=o,theta=t,membership=g,parent=m,
        runtime_identity={},candidate_sha='a'*64,completed_games=8,accepted=True,cycle=2,seed_parent={})


def test_sampling_changes_without_weight_updates():
    used=[]
    for i in range(1,50):
        seeds=cycle_seeds(i);used.extend([seeds['training'],*seeds['confirmation']])
        assert seeds['combat'] not in used
    assert len(used)==len(set(used))
    assert cycle_seeds(1)['directions']!=cycle_seeds(2)['directions']


@pytest.mark.parametrize('cycle',[0,-1,True,1.2,1000001])
def test_bad_cycles(cycle):
    with pytest.raises(ValueError):cycle_seeds(cycle)


def metrics(score,damage=0,taken=0):
    return dict(curriculum_score=score,damage_dealt_hp=damage,damage_taken_hp=taken)


def test_confirmation_requires_real_out_of_training_gain():
    a={'parent':metrics(0),'candidate':metrics(.1)}
    b={'parent':metrics(0),'candidate':metrics(0)}
    assert confirmation_pass([a,b])
    assert not confirmation_pass([b,b])
    assert not confirmation_pass([a])
    assert not confirmation_pass([a,{'parent':metrics(.2),'candidate':metrics(.1)}])
    assert not confirmation_pass([a,{'parent':metrics(.2,20),'candidate':metrics(.3,10)}])
    assert not confirmation_pass([a,{'parent':metrics(.2),'candidate':metrics(float('nan'))}])


def test_reward_and_clock_contract_is_the_approved_design():
    assert json.loads((ROOT/'configs/paired_training_v1.json').read_text())==CONFIG
    assert CONFIG['combat']==dict(id='outcome-hp-epsilon002-v1',win=1.,draw=0.,loss=-1.,hp_weight=.02)
    assert CONFIG['curriculum']==dict(id='approach-hit-damage-v1',progress=.1,hit=.4,damage=.5)
    assert CONFIG['neural_window_ms']==20 and CONFIG['decision_interval_frames']==60


def summary(tmp_path,monkeypatch):
    p,m,*_=state(tmp_path)
    for k,v in dict(GITHUB_REPOSITORY=release.REPO,GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='push',GITHUB_SHA='a'*40,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1').items():monkeypatch.setenv(k,v)
    return dict(status='PASS',experiment=EXPERIMENT,source_commit='a'*40,source_run_id='123',source_run_attempt='1',
        auto_promotion=False,candidate_only=True,strength_claim=False,parent_source_unchanged=True,cycle=1,accepted_update=False,state=m,config_sha256=digest(CONFIG))


@pytest.mark.parametrize('key,value',[('GITHUB_REPOSITORY','Unjuno/live'),('GITHUB_REF','refs/heads/feature'),('GITHUB_EVENT_NAME','pull_request'),('GITHUB_SHA','b'*40),('GITHUB_RUN_ID','124')])
def test_publication_scope(tmp_path,monkeypatch,key,value):
    s=summary(tmp_path,monkeypatch);monkeypatch.setenv(key,value)
    with pytest.raises(ValueError):release.require_publication(s)


def test_publication_parent_guard(tmp_path,monkeypatch):
    s=summary(tmp_path,monkeypatch);release.require_publication(s);release.require_parent(s,None)
    old=deepcopy(s);s['cycle']=2;s['state']['cycle']=2;s['state']['parent_cycle']=1
    s['state']['parent_state_file_sha256']=old['state']['state_file_sha256']
    release.require_parent(s,old)
    old['cycle']=3
    with pytest.raises(ValueError):release.require_parent(s,old)
    with pytest.raises(ValueError):release.require_parent(s,None)


def test_immutable_asset_collision(tmp_path,monkeypatch):
    p=tmp_path/'after.mp4';p.write_bytes(b'recorded bytes')
    def forbidden(*args):raise AssertionError('must not upload')
    monkeypatch.setattr(release,'call',forbidden)
    release.upload_immutable('paired-cycle-1-1',p,{'assets':[{'name':p.name,'digest':'sha256:'+release.sha(p)}]})
    with pytest.raises(ValueError):release.upload_immutable('paired-cycle-1-1',p,{'assets':[{'name':p.name,'digest':'sha256:'+'0'*64}]})
