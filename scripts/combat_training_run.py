#!/usr/bin/env python3
"""Bounded real-game candidate experiment: paired evaluation, train, evaluate.

This process cannot publish releases or modify the repository. CI publishes its
completed artifacts separately, on main only. No Vercel or approved-state writes.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from connectome_fighter.combat_reward import paired_evaluation_suite_gate

REWARD = 'R2e-combat-v1'
REPO = 'Unjuno/connectome-fighter'
READOUT_MODE = 'ema-residual'
READOUT_CONTRACT = 'malecns-temporal-readout-v1'
MATCH_STATUS = 'COMPLETED_WITH_VALIDATED_EXPERIMENTAL_READOUT_TRACES'
SCHEDULE_CONTRACT = {
    'mode': 'bounded-self-chain-with-hourly-watchdog',
    'self_chain_hold_seconds': 120,
    'watchdog_cron': '17 * * * *',
    'guaranteed_interval': False,
}
LEGACY_EVALUATION = {'opponent':'ZEN','seed_p1':800101,'seed_p2':20202}
VALIDATION_SUITE = (
    {'case_id':'zen-validation-v1','opponent':'ZEN','seed_p1':810101,'seed_p2':31001},
    {'case_id':'lud-validation-v1','opponent':'LUD','seed_p1':810202,'seed_p2':31002},
    {'case_id':'nez-validation-v1','opponent':'NEZ','seed_p1':810303,'seed_p2':31003},
)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
    return h.hexdigest()


def write(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')


def now(): return datetime.now(timezone.utc).isoformat()


def stop(proc):
    if proc.poll() is not None: return
    try: os.killpg(proc.pid,signal.SIGTERM); proc.wait(timeout=5)
    except ProcessLookupError: pass
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--source-archive',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout-seconds',type=int,default=1050)
    args=p.parse_args()
    if os.environ.get('CI')!='true' or os.environ.get('VERCEL'): p.error('standalone CI only')
    if not 180<=args.timeout_seconds<=1200: p.error('timeout must be 180..1200 seconds')
    runtime=args.runtime_root.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+args.timeout_seconds
    manifest=json.loads((runtime/'manifest.json').read_text())
    assert manifest['canonical_model']=='MaleCNS v1.0 + pinned Shiu LIF'
    assert manifest['learning_enabled'] is False and manifest['policy_pixel_access'] is False
    ref=runtime/(runtime/'runtime/python310.path').read_text().strip()
    bridge=runtime/(runtime/'runtime/python311.path').read_text().strip()
    assert str(ref)==manifest['brian2_expected_sys_executable']
    assert manifest['brian2_compilerless_reuse_verified'] is True
    audit={}
    for name,key in [('data/malecns-shiu-strict-v1/connectivity.parquet','adapter_connectivity_sha256'),('shiu/model.py','shiu_model_sha256'),('fightingice/FightingICE.jar','fightingice_jar_sha256')]:
        audit[name]={'actual':sha(runtime/name),'expected':manifest[key]}
        assert audit[name]['actual']==audit[name]['expected'],name
    interface=json.loads((runtime/'data/interface.json').read_text());embedded=interface.pop('interface_sha256')
    assert hashlib.sha256(json.dumps(interface,sort_keys=True,separators=(',',':')).encode()).hexdigest()==embedded==manifest['interface_sha256']
    write(out/'asset-audit.json',audit)
    for name in ('src','scripts','configs'):
        shutil.copytree(ROOT/name,runtime/'repo'/name,dirs_exist_ok=True)
    source=out/'source'
    source.mkdir(exist_ok=False)
    with tarfile.open(args.source_archive) as archive:
        archive.extractall(source,filter='data')
    origin=source/'state/GARNET.npz'
    metadata=json.loads(origin.with_suffix('.npz.json').read_text())
    assert sha(origin)==metadata['state_sha256'] and metadata['character']=='GARNET'
    assert metadata['model']=='KC-MBON-valence-depression-v0'
    parent=dict(metadata)
    before_source={str(f.relative_to(source)):sha(f) for f in source.rglob('*') if f.is_file()}
    state=out/'checkpoint/state/GARNET.npz';state.parent.mkdir(parents=True)
    env=dict(os.environ,PYTHONPATH=f"{runtime/'repo/src'}:{runtime/'runtime/site311'}",
             PATH=f"{runtime/'runtime/jre21/bin'}:{os.environ['PATH']}",
             OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    wrapper=out/'reference-python'
    import shlex
    wrapper.write_text('#!/bin/sh\nexport PYTHONPATH='+shlex.quote(str(runtime/'runtime/site310'))+'\nexec '+shlex.quote(str(ref))+' "$@"\n');wrapper.chmod(0o755)
    def run(command,name):
        with (out/(name+'.log')).open('wb') as log:
            proc=subprocess.Popen([str(v) for v in command],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                rc=proc.wait(timeout=max(1,deadline-time.monotonic()))
                if rc: raise RuntimeError(f'{name} exited {rc}; see {name}.log')
            finally: stop(proc)
    cfg=ROOT/'configs/plasticity_combat_v1.json'
    old_cfg=ROOT/'configs/plasticity_valence_v0.json'
    prepare='''import json,sys,shutil; from pathlib import Path
from connectome_fighter.combat_checkpoint import config_from_json,fork_reward
from connectome_fighter.valence_plasticity import load_state
source,dest,old_path,new_path=map(Path,sys.argv[1:]);meta=json.loads(source.with_suffix('.npz.json').read_text());new=config_from_json(json.loads(new_path.read_text()))
if meta['reward_id']=='R2d-v0':
    fork_reward(source,dest,config_from_json(json.loads(old_path.read_text())),new)
else:
    assert meta['reward_id']=='R2e-combat-v1'
    load_state(source,expected_character='GARNET',n_candidates=meta['n_candidates'],expected_candidate_sha256=meta['candidate_sha256'],config=new)
    shutil.copy2(source,dest);shutil.copy2(source.with_suffix('.npz.json'),dest.with_suffix('.npz.json'))
'''
    run([bridge,'-c',prepare,origin,state,old_cfg,cfg],'prepare-reward-fork')
    base=runtime/'data/malecns-shiu-strict-v1'
    candidates=runtime/'data/malecns-valence-v1/kc_mbon_valence_candidates.parquet'
    def materialize(name):
        adapter=out/name
        run([bridge,runtime/'repo/scripts/materialize_malecns_valence_adapter.py','--base-adapter',base,'--candidates',candidates,'--state',state,'--character','GARNET','--plasticity-config',cfg,'--out',adapter],name)
        return adapter
    before_adapter=materialize('before-adapter')
    def match(name,adapter,opponent,seed1,seed2,train=False,video=False):
        game_dir=runtime/'fightingice'
        with (out/(name+'-game.log')).open('wb') as log:
            game=subprocess.Popen(['java','-cp','FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*','Main','--headless-mode','--pyftg-mode','--input-sync','--limithp','400','400','--port','31415','-r','1','-f','3600'],cwd=game_dir,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                for _ in range(90):
                    if game.poll() is not None: raise RuntimeError('game exited before startup')
                    if 'Socket server is started' in (out/(name+'-game.log')).read_text(errors='replace'):break
                    time.sleep(.5)
                else:raise TimeoutError('game startup timeout')
                cmd=[bridge,runtime/'repo/scripts/run_game_malecns_lif.py','--host','127.0.0.1','--port','31415','--character-p1','GARNET','--character-p2',opponent,'--seed-p1',str(seed1),'--seed-p2',str(seed2),'--reference-python',wrapper,'--reference-model',runtime/'shiu/model.py','--adapter-dir',base,'--adapter-dir-p1',adapter,'--interface',runtime/'data/interface.json','--decision-interval','60','--readout-mode-p1',READOUT_MODE,'--readout-mode-p2','canonical','--games','1','--expected-rounds','1','--timeout',str(max(1,min(600,int(deadline-time.monotonic())))),'--run-id',name,'--out',out/'matches']
                if train: cmd+=['--trainable-trace']
                if video: cmd+=['--spectator-video',out/(name+'.mp4'),'--spectator-fps','10']
                run(cmd,name)
            finally:stop(game)
        folder=out/'matches'/name
        status=json.loads((folder/'status.json').read_text())
        assert status['status']==MATCH_STATUS
        assert status['canonical'] is False
        assert status['readout_modes']==[READOUT_MODE,'canonical']
        assert status['readout_contract']==READOUT_CONTRACT and status['readout_game_state_used'] is False
        assert status['learning_performed'] is False and status['trace_trainable'] is train
        assert status['completed_rounds_per_agent']==[1,1]
        assert len(status['workers'])==2 and all(w['neurons']==156675 and w['synapses']==6025920 for w in status['workers'])
        rows=[json.loads(line) for line in (folder/'p1.jsonl').read_text().splitlines() if line.strip()]
        assert len(rows)==1 and rows[0]['terminated'] is True and rows[0]['truncated'] is False
        trace=rows[0];hps=[max(0,v) for v in trace['remaining_hps']]
        assert trace['elapsed_frame']==3600 or min(hps)==0
        transitions=trace['transitions'];initial=transitions[0]['display']
        return {'winner':'GARNET' if hps[0]>hps[1] else opponent if hps[0]<hps[1] else 'DRAW',
                'p1_hp':hps[0],'p2_hp':hps[1],'elapsed_frame':trace['elapsed_frame'],'elapsed_seconds':trace['elapsed_frame']/60,
                'ended_by':'KO' if min(hps)==0 else 'TIME_LIMIT',
                'damage_dealt_hp':max(0,initial['p2']['hp']-hps[1]),'damage_taken_hp':max(0,initial['p1']['hp']-hps[0]),
                'no_damage_draw':hps==[400,400], 'decision_count':len(transitions),
                'readout_mode':READOUT_MODE,'readout_contract':READOUT_CONTRACT,
                'requested_action_counts':dict(Counter(str(t['action']) for t in transitions))}
    def evaluate_suite(prefix,adapter):
        rows=[]
        for case in VALIDATION_SUITE:
            metrics=match(f"{prefix}-{case['case_id']}",adapter,case['opponent'],case['seed_p1'],case['seed_p2'])
            rows.append({**case,'metrics':metrics})
        return rows
    started=now();clock=time.monotonic()
    run_id=os.environ.get('GITHUB_RUN_ID','local');run_url=f'https://github.com/{REPO}/actions/runs/{run_id}'
    write(out/'environment.json',{'started_at':started,'tested_commit':os.environ.get('GITHUB_SHA'),
          'python':sys.version,'runtime_manifest':manifest,'reward':REWARD,'game_frames':3600,'decision_interval_frames':60,
          'readout_mode_p1':READOUT_MODE,'readout_mode_p2':'canonical','readout_contract':READOUT_CONTRACT,
          'legacy_evaluation':LEGACY_EVALUATION,'acceptance_validation_suite':VALIDATION_SUITE,
          'synthetic_neural_fixture':False,'candidate_only':True,'auto_promotion':False,
          'pipeline':'legacy-anchor-before/validation-suite-before/train/validation-suite-after/legacy-anchor-after/robust-acceptance-gate',
          'training_seed_strategy':'generation-plus-github-run-id-salt','source_archive_sha256':sha(args.source_archive),
          'selected_dependency_descriptor':json.loads((out/'dependencies.json').read_text()) if (out/'dependencies.json').exists() else None})
    result={'status':'FAIL','accepted_update':False,'reward_id':REWARD,'source_run_url':run_url,'readout_mode':READOUT_MODE,'readout_contract':READOUT_CONTRACT}
    try:
        frozen=sha(state)
        before=match('before',before_adapter,LEGACY_EVALUATION['opponent'],LEGACY_EVALUATION['seed_p1'],LEGACY_EVALUATION['seed_p2'],video=True)
        validation_before=evaluate_suite('validation-before',before_adapter)
        assert sha(state)==frozen
        generation=int(metadata['generation']);opponents=('ZEN','LUD','NEZ');opponent=opponents[generation%3]
        try: attempt_salt=int(run_id)%100000
        except ValueError: attempt_salt=0
        train_seed=900001+generation*101+attempt_salt
        train_seed_p2=700001+generation*103+attempt_salt*3
        training=match('training',before_adapter,opponent,train_seed,train_seed_p2,train=True)
        assert sha(state)==frozen
        run([bridge,runtime/'repo/scripts/update_malecns_valence_plasticity.py','--character','GARNET','--side','1','--round-trace',out/'matches/training/p1.jsonl','--spikes',out/'matches/training/p1-brain/spikes.parquet','--candidates',candidates,'--reward-config',ROOT/'configs/reward_r2e_combat_v1.json','--plasticity-config',cfg,'--state',state,'--out-summary',out/'update.json'],'update')
        update=json.loads((out/'update.json').read_text());assert update['status']=='PASS'
        assert update['updates']['potentiated_edges']==0 and update['invariants']['topology_changed'] is False and update['invariants']['sign_changed'] is False
        after_adapter=materialize('after-adapter');after_hash=sha(state)
        validation_after=evaluate_suite('validation-after',after_adapter)
        after=match('after',after_adapter,LEGACY_EVALUATION['opponent'],LEGACY_EVALUATION['seed_p1'],LEGACY_EVALUATION['seed_p2'],video=True)
        assert sha(state)==after_hash
        assert before_source=={str(f.relative_to(source)):sha(f) for f in source.rglob('*') if f.is_file()}
        meta=json.loads(state.with_suffix('.npz.json').read_text());assert meta['generation']==generation+1
        reward_config=json.loads((ROOT/'configs/reward_r2e_combat_v1.json').read_text())
        gate_cases=[]
        for before_case,after_case in zip(validation_before,validation_after,strict=True):
            assert before_case['case_id']==after_case['case_id']
            gate_cases.append({
                'case_id':before_case['case_id'],'opponent':before_case['opponent'],
                'seed_p1':before_case['seed_p1'],'seed_p2':before_case['seed_p2'],
                'before':before_case['metrics'],'after':after_case['metrics'],
            })
        gate=paired_evaluation_suite_gate(gate_cases,reward_config)
        gate.update({'protocol':'fixed-three-opponent-validation-v1',
                     'parent_generation':generation,'proposed_generation':meta['generation'],
                     'parent_state_sha256':parent['state_sha256'],'proposed_state_sha256':after_hash})
        write(out/'acceptance.json',gate)
        if not gate['accepted_update']:
            result={'status':'REJECTED','accepted_update':False,'reward_id':REWARD,'source_run_url':run_url,
                    'generation':generation,'proposed_generation':meta['generation'],'readout_mode':READOUT_MODE,
                    'readout_contract':READOUT_CONTRACT,'before':before,'training':training,'after':after,
                    'validation_before':validation_before,'validation_after':validation_after,
                    'acceptance_gate':gate,'changed_edges':update['updates']['changed_edges'],
                    'parent_state_sha256':parent['state_sha256'],'proposed_state_sha256':after_hash,
                    'training_seed':train_seed,'training_seed_p2':train_seed_p2,'training_attempt_salt':attempt_salt,
                    'auto_promotion':False,'pipeline_seconds':time.monotonic()-clock}
            print(json.dumps(result,indent=2))
            return 0
        publish=out/'publish';publish.mkdir()
        package=out/'package';(package/'state').mkdir(parents=True)
        shutil.copy2(state,package/'state/GARNET.npz');shutil.copy2(state.with_suffix('.npz.json'),package/'state/GARNET.npz.json')
        write(package/'parent.json',{'state_sha256':parent['state_sha256'],'generation':generation,'reward_id':parent['reward_id'],'config_sha256':parent['config_sha256'],'metadata':parent})
        write(package/'update.json',update)
        archive_name=f"garnet-g{meta['generation']:06d}-{meta['state_sha256'][:16]}.tar.gz"
        with tarfile.open(publish/archive_name,'w:gz') as tar:tar.add(package,arcname='.')
        archive_sha=sha(publish/archive_name)
        status={'schema_version':1,'kind':'canonical-continuous-training-candidate','status':'candidate-only-not-arena-approved',
                'character':'GARNET','generation':meta['generation'],'matches':meta['matches'],'state_sha256':meta['state_sha256'],
                'model':meta['model'],'reward_id':REWARD,'opponent':opponent,'source_kind':'combat-training-v1',
                'source_run_url':run_url,'served_by_vercel':False,'auto_promotion':False,'updated_at':now(),
                'readout_mode':READOUT_MODE,'readout_contract':READOUT_CONTRACT,
                'match_status':MATCH_STATUS,'signal_summary':update['signals'],'update_summary':update['updates'],
                'parent_generation':generation,'parent_reward_id':parent['reward_id'],'parent_state_sha256':parent['state_sha256'],
                'archive_file':archive_name,'archive_sha256':archive_sha,'schedule_minutes':None,'schedule_contract':SCHEDULE_CONTRACT,
                'actual_pipeline_seconds':time.monotonic()-clock,'training_seed':train_seed,'training_seed_p2':train_seed_p2,
                'training_attempt_salt':attempt_salt,'accepted_update':True,'acceptance_gate':gate,
                'combat_metrics':{'before':before,'training':training,'after':after,
                                  'validation_before':validation_before,'validation_after':validation_after},
                'interpretation_boundary':'Experimental R2e candidate using the held-out-selected EMA-residual P1 readout. Publication now requires improvement across a small fixed ZEN/LUD/NEZ validation suite; this is still not proof of general fighting strength or biological validity.'}
        write(publish/'training-manifest.json',status);write(publish/'training-status.json',status)
        video_tag=f'combat-evaluation-{run_id}'
        for phase,metrics,g in [('before',before,generation),('after',after,meta['generation'])]:
            video=out/(phase+'.mp4')
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
            stream=next(s for s in probe['streams'] if s['codec_type']=='video');duration=float(probe['format']['duration'])
            assert stream['codec_name']=='h264' and (stream['width'],stream['height'])==(960,640) and 0<duration<=75 and video.stat().st_size>10000
            shutil.copy2(video,publish/(phase+'.mp4'))
            evaluation={'schema_version':2,'kind':'post-update-candidate-round-evaluation','status':'COMPLETED',
                        'candidate_only':True,'auto_promotion':False,'served_by_vercel':False,'policy_pixel_access':False,
                        'character':'GARNET','opponent':'ZEN','generation':g,'matches':meta['matches'] if phase=='after' else parent['matches'],
                        'state_sha256':after_hash if phase=='after' else frozen,'model':meta['model'],'reward_id':REWARD,
                        'readout_mode':READOUT_MODE,'readout_contract':READOUT_CONTRACT,
                        'evaluated_at':now(),'source_training_run_url':run_url,'comparison_phase':phase,
                        'evaluation':{'protocol':'fixed-full-round-v2','rounds':1,'fixed_opponent':True,'seed_p1':800101,'seed_p2':20202,'round_frame_limit':3600,'nominal_game_fps':60,'configured_round_limit_seconds':60,'decision_interval_frames':60},
                        'result':metrics,'video':{'asset_url':f'https://github.com/{REPO}/releases/download/{video_tag}/{phase}.mp4','codec':'h264','width':960,'height':640,'fps':10,'duration_seconds':duration,'bytes':video.stat().st_size,'sha256':sha(video)},
                        'interpretation_boundary':'Actual frozen before/after legacy ZEN comparability anchor using the held-out-selected EMA-residual P1 readout. Candidate acceptance uses a separate fixed ZEN/LUD/NEZ validation suite; this replay is not proof of generalization or production LIVE.'}
            write(publish/('evaluation-status.json' if phase=='after' else 'evaluation-previous.json'),evaluation)
        write(publish/'publication.json',{'video_tag':video_tag,'checkpoint_tag':'combat-training-v1','archive_file':archive_name,'generation':meta['generation'],'source_run_id':run_id,'source_commit':os.environ.get('GITHUB_SHA')})
        result={'status':'PASS','accepted_update':True,'reward_id':REWARD,'source_run_url':run_url,'generation':meta['generation'],
                'readout_mode':READOUT_MODE,'readout_contract':READOUT_CONTRACT,
                'before':before,'training':training,'after':after,
                'validation_before':validation_before,'validation_after':validation_after,
                'acceptance_gate':gate,'changed_edges':update['updates']['changed_edges'],
                'training_seed':train_seed,'training_seed_p2':train_seed_p2,'training_attempt_salt':attempt_salt,
                'new_state_sha256':after_hash,'parent_state_sha256':parent['state_sha256'],
                'auto_promotion':False,'pipeline_seconds':time.monotonic()-clock}
        print(json.dumps(result,indent=2))
    finally:
        result['finished_at']=now();write(out/'result.json',result)
    return 0

if __name__=='__main__':raise SystemExit(main())