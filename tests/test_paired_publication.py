"""Local engineering publication tests. No hosted CI or deployment claim."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import pytest
from connectome_fighter.paired_rollout import write_json, digest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('paired_io',ROOT/'scripts/paired_rollout_io.py')
io=importlib.util.module_from_spec(spec);spec.loader.exec_module(io)


def environment():
    return {'GITHUB_REPOSITORY':io.REPO,'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'schedule',
            'GITHUB_RUN_ID':'11','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40}


def publication():
    return {'run_id':'11','attempt':'1','commit':'a'*40,'tag':'paired-cycle-11-1'}


def test_writer_accepts_exact_main_run():io.writer_guard(publication(),environment())


@pytest.mark.parametrize('key,value',[('GITHUB_REPOSITORY','Unjuno/live'),('GITHUB_REF','refs/pull/1/merge'),
 ('GITHUB_EVENT_NAME','pull_request'),('GITHUB_EVENT_NAME','workflow_run'),('GITHUB_SHA','b'*40),
 ('GITHUB_RUN_ID','12'),('GITHUB_RUN_ATTEMPT','2'),('CONNECTOME_TRAINING_PAUSED','true')])
def test_writer_rejects_wrong_boundary(key,value):
    env=environment();env[key]=value
    with pytest.raises(ValueError):io.writer_guard(publication(),env)


def test_release_name_cannot_redirect_publication():
    p=publication();p['tag']='arena-inference-latest'
    with pytest.raises(ValueError):io.writer_guard(p,environment())


@pytest.mark.parametrize('mutation',['missing','digest','ambiguous','size'])
def test_asset_selection_requires_one_complete_digest(mutation):
    a={'id':1,'name':'checkpoint.tar.gz','state':'uploaded','size':100,'digest':'sha256:'+'a'*64}
    rows=[a]
    if mutation=='missing':rows=[]
    if mutation=='digest':a['digest']=''
    if mutation=='ambiguous':rows=[a,a]
    if mutation=='size':a['size']=0
    with pytest.raises(ValueError):io.asset({'assets':rows},'checkpoint.tar.gz')


def test_download_checks_actual_bytes(tmp_path,monkeypatch):
    monkeypatch.setattr(io,'command',lambda args,**kw:kw['stdout'].write(b'wrong'))
    with pytest.raises(ValueError):io.download({'id':1,'digest':'sha256:'+'a'*64,'size':5},tmp_path/'asset')


def test_failed_source_fetch_not_replaced_with_seed(monkeypatch,tmp_path):
    monkeypatch.setattr(io,'remote_view',lambda: (_ for _ in ()).throw(RuntimeError('HTTP 403')))
    with pytest.raises(RuntimeError):io.fetch_inputs(tmp_path/'new')
    assert not (tmp_path/'new/source.tar.gz').exists()


def test_missing_and_non404_api_errors_are_different(monkeypatch):
    def response(err):
        return type('Response',(),{'returncode':1,'stderr':err,'stdout':''})()
    monkeypatch.setattr(io.subprocess,'run',lambda *a,**kw:response('gh: Not Found (HTTP 404)'))
    assert io.api('contents/site/data/paired-latest.json?ref=main',optional=True) is None
    monkeypatch.setattr(io.subprocess,'run',lambda *a,**kw:response('gh: API rate limit (HTTP 403)'))
    with pytest.raises(RuntimeError):io.api('contents/site/data/paired-latest.json?ref=main',optional=True)


def test_real_local_git_retry_preserves_concurrent_unrelated_edit(tmp_path,monkeypatch):
    # The connected remote identity is mocked; the Git commits, race and pushes
    # use a real local bare repository. No GitHub/network publication occurs.
    from test_paired_rollout import view
    old_run=io.subprocess.run;old_output=io.subprocess.check_output
    remote=tmp_path/'remote.git';work=tmp_path/'work';racer=tmp_path/'racer'
    def git(*args,cwd=None):
        return old_run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True)
    git('init','--bare','--initial-branch=main',str(remote))
    git('clone',str(remote),str(work))
    for key,value in [('user.name','fixture'),('user.email','fixture@example.invalid')]:git('config',key,value,cwd=work)
    (work/'user.txt').write_text('initial\n');git('add','user.txt',cwd=work);git('commit','-m','initial',cwd=work);git('push','origin','main',cwd=work)
    git('clone',str(remote),str(racer))
    for key,value in [('user.name','fixture'),('user.email','fixture@example.invalid')]:git('config',key,value,cwd=racer)
    pub=tmp_path/'pub';pub.mkdir();write_json(pub/'paired-latest.json',view())
    raced=False
    def check(args,**kw):
        if args==['git','remote','get-url','origin']:return 'https://github.com/Unjuno/connectome-fighter\n'
        return old_output(args,**kw)
    def run(args,**kw):
        nonlocal raced
        if args[0]=='git' and 'push' in args and 'HEAD:main' in args and not raced:
            raced=True
            (racer/'user.txt').write_text('concurrent edit\n')
            git('add','user.txt',cwd=racer);git('commit','-m','concurrent',cwd=racer);git('push','origin','main',cwd=racer)
        return old_run(args,**kw)
    monkeypatch.setattr(io.subprocess,'check_output',check)
    monkeypatch.setattr(io.subprocess,'run',run)
    monkeypatch.setattr(io.time,'sleep',lambda _:None)
    monkeypatch.chdir(work)
    io.publish_view(pub,{})
    assert raced
    assert git('--git-dir',str(remote),'show','main:user.txt').stdout=='concurrent edit\n'
    result=git('--git-dir',str(remote),'show','main:site/data/paired-latest.json').stdout
    assert 'paired-evaluation-ready' in result


def package_fixture(tmp_path):
    """Artificial full-cycle fixture for serialization, never a real-game claim."""
    import numpy as np
    from test_paired_rollout import parent
    from test_paired_search import episode
    from connectome_fighter.paired_rollout import save_checkpoint,seeds,PROTOCOL_SHA256,file_hash,weights_hash
    from connectome_fighter.paired_search import score_round
    out=tmp_path/'cycle';out.mkdir()
    par=parent(tmp_path)
    meta=save_checkpoint(out/'candidate',par,np.arange(8),par.multipliers,False,'a'*64,[],'curriculum')
    plan=seeds(1);metrics=score_round(*episode());entries=[]
    names=['curriculum-before','curriculum-repeat']+[f'probe-{j}-{s}' for j in range(4) for s in ('plus','minus')]+['combat-before','combat-after']
    for name in names:
        folder=out/'matches'/name;folder.mkdir(parents=True)
        row,samples=episode()
        (folder/'p1.jsonl').write_text(__import__('json').dumps(row)+'\n')
        (folder/'observed-frames.jsonl').write_text('\n'.join(__import__('json').dumps(s) for s in samples)+'\n')
        opponent='canonical' if name.startswith('combat-') else 'neutral'
        seed=plan['combat'] if opponent=='canonical' else plan['training']
        workers=[{'neurons':156675,'synapses':6025920}]*(2 if opponent=='canonical' else 1)
        write_json(folder/'result.json',{'status':'PASS','metrics':metrics,'completed_rounds':[1,1], 'workers':workers,
                    'policy_pixel_access':False,'learning_performed':False,'synthetic_neural_fixture':False,
                    'seed_p1':seed,'opponent_mode':opponent})
        item={'name':name,'seed':seed,'opponent':opponent,'metrics':metrics,'multipliers_sha256':weights_hash(par.multipliers)}
        if name.startswith('combat-'):
            video=folder/'screen.mp4';video.write_bytes(b'ARTIFICIAL ENCODING FIXTURE, NOT VIDEO')
            item['video']={'path':str(video.relative_to(out)),'sha256':file_hash(video),'bytes':video.stat().st_size,'recording_seconds':60}
        entries.append(item)
    write_json(out/'matches-summary.json',entries)
    result={'status':'PASS','rollout':io.ROLLOUT,'checkpoint':meta,'parent_source_unchanged':True,'strength_claim':False,
            'completed_games':12,'phase':'curriculum','accepted_update':False,'update_reason':'zero paired signal','cycle_index':1,
            'parent_weights_sha256':weights_hash(par.multipliers),'combat_before':metrics,'combat_after':metrics,'actual_pipeline_seconds':1,
            'plus_scores':[0]*4,'minus_scores':[0]*4,'gradient':[0]*8,'proposal_step':[0]*8}
    write_json(out/'result.json',result)
    write_json(out/'design.json',{'tested_checkout':'a'*40,'protocol_sha256':PROTOCOL_SHA256,'seed_plan':plan,'paired_directions':np.ones((4,8)).tolist()})
    write_json(out/'dependencies.json',{'previous_view':None})
    return out


def test_package_coherent_artificial_cycle_without_remote_calls(tmp_path,monkeypatch):
    out=package_fixture(tmp_path)
    monkeypatch.setattr(io,'api',lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected network')))
    v=io.package(out,run_id='123',attempt='1',commit='a'*40)
    assert v['cycle_index']==1 and v['accepted_update_count']==0
    assert v['previous']['generation']==v['latest']['generation']==11
    assert v['latest']['video']['asset_url'].endswith('/paired-cycle-123-1/after.mp4')
    assert (out/'publish/trace-evidence.zip').exists()


@pytest.mark.parametrize('kind',['video','checkpoint','seed','gradient','score','acceptance'])
def test_package_rejects_corruption_or_plan_mismatch(tmp_path,kind):
    out=package_fixture(tmp_path)
    if kind=='video':(out/'matches/combat-after/screen.mp4').write_bytes(b'corrupt')
    if kind=='checkpoint':(out/'candidate/search-state.npz').write_bytes(b'corrupt')
    if kind=='seed':
        rows=io.read(out/'matches-summary.json');rows[0]['seed']+=1;write_json(out/'matches-summary.json',rows)
    if kind in ('gradient','acceptance'):
        result=io.read(out/'result.json')
        if kind=='gradient':result['gradient'][0]=1
        else:result['accepted_update']=True
        write_json(out/'result.json',result)
    if kind=='score':
        rows=io.read(out/'matches-summary.json');rows[0]['metrics']['curriculum_score']=1;write_json(out/'matches-summary.json',rows)
    with pytest.raises(ValueError):io.package(out,run_id='123',attempt='1',commit='a'*40)
