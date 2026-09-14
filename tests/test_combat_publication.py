"""Local Git race fixtures; no network, biological or production-performance claim."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('combat_view', ROOT/'scripts/publish_combat_view.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def payload():
    status = {'kind':'canonical-continuous-training-candidate','status':'candidate-only-not-arena-approved',
              'served_by_vercel':False,'auto_promotion':False,'character':'GARNET','matches':10,
              'generation':10,'state_sha256':'b'*64,'parent_generation':9,'parent_state_sha256':'a'*64,
              'reward_id':'R2e-combat-v1','source_run_url':'https://github.com/Unjuno/connectome-fighter/actions/runs/1'}
    common={'status':'COMPLETED','candidate_only':True,'auto_promotion':False,'served_by_vercel':False,
            'policy_pixel_access':False,'source_training_run_url':status['source_run_url'],
            'evaluation':{'protocol':'fixed-full-round-v2'}}
    return {'training-status.json':status,
            'evaluation-status.json':dict(common,comparison_phase='after',generation=10,state_sha256='b'*64),
            'evaluation-previous.json':dict(common,comparison_phase='before',generation=9,state_sha256='a'*64)}


def current():
    return dict(payload()['training-status.json'],generation=9,matches=9,state_sha256='a'*64,reward_id='R2d-v0')


@pytest.mark.parametrize('change',[{'generation':11},{'state_sha256':'c'*64},{'generation':8}])
def test_reject_wrong_parent_newer_or_fork(change):
    with pytest.raises(ValueError):m.validate_parent(dict(current(),**change),payload()['training-status.json'])


def test_idempotent_and_parent_accepted():
    p=payload();m.validate_payload(p);m.validate_parent(current(),p['training-status.json'])
    m.validate_parent(p['training-status.json'],p['training-status.json'])


@pytest.mark.parametrize('field,value',[('generation',99),('state_sha256','c'*64),('policy_pixel_access',True),('comparison_phase','before')])
def test_reject_unbound_after(field,value):
    p=payload();p['evaluation-status.json'][field]=value
    with pytest.raises(ValueError):m.validate_payload(p)


def run(path,*args):
    return subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True,text=True).stdout


def setup(tmp_path):
    bare=tmp_path/'remote.git';bare.mkdir();run(bare,'init','--bare','--initial-branch=main')
    seed=tmp_path/'seed';run(tmp_path,'clone',str(bare),str(seed))
    run(seed,'config','user.name','Fixture');run(seed,'config','user.email','fixture@example.invalid')
    data=seed/'site/data';data.mkdir(parents=True)
    for name in m.NAMES:(data/name).write_text(json.dumps(current() if name=='training-status.json' else {'old':True}))
    m.append_history(data/'training-status.json',data/'training-history.json')
    (seed/'untouched.txt').write_text('original')
    run(seed,'add','.');run(seed,'commit','-m','initial');run(seed,'push','origin','main')
    worker=tmp_path/'worker';run(tmp_path,'clone',str(bare),str(worker))
    return bare,seed,worker


def test_actual_git_race_preserves_concurrent_changes(tmp_path):
    bare,seed,worker=setup(tmp_path)
    def intervene(attempt):
        if attempt:return
        (seed/'untouched.txt').write_text('concurrent user update')
        (seed/'site/data/evaluation-status.json').write_text('{"legacy_evaluation":"concurrent"}')
        run(seed,'add','.');run(seed,'commit','-m','concurrent change');run(seed,'push','origin','main')
    result=m.publish(worker,payload(),before_push=intervene)
    assert result['status']=='PASS' and result['attempts']==2
    out=tmp_path/'out';run(tmp_path,'clone',str(bare),str(out))
    assert (out/'untouched.txt').read_text()=='concurrent user update'
    h=json.loads((out/'site/data/training-history.json').read_text());assert [e['generation'] for e in h['entries']]==[9,10]
    assert json.loads((out/'site/data/evaluation-status.json').read_text())==payload()['evaluation-status.json']
    assert m.publish(worker,payload())['publication']=='already-current'
    assert len(run(worker,'worktree','list','--porcelain').split('worktree '))-1==1


def test_concurrent_newer_candidate_is_never_overwritten(tmp_path):
    bare,seed,worker=setup(tmp_path)
    def intervene(attempt):
        (seed/'site/data/training-status.json').write_text(json.dumps(dict(current(),generation=11,matches=11,state_sha256='c'*64)))
        run(seed,'add','.');run(seed,'commit','-m','newer candidate');run(seed,'push','origin','main')
    with pytest.raises(ValueError):m.publish(worker,payload(),before_push=intervene)
    run(seed,'pull','--ff-only');assert json.loads((seed/'site/data/training-status.json').read_text())['generation']==11
