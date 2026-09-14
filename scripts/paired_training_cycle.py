#!/usr/bin/env python3
"""One persistent paired-training cycle, without remote writes.

Reuses the audited game/materializer and reward functions. P1 remains actual
MaleCNS/Shiu LIF. A new cycle changes sampling, not reward coefficients or clocks.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from paired_search_experiment import materialize, sha, write, stop
from connectome_fighter.paired_search import group_indices, multipliers, propose
from connectome_fighter.paired_training import (
    EXPERIMENT, CONFIG, digest, cycle_seeds, load_search, save_search,
    weights_sha, confirmation_pass,
)
from connectome_fighter.combat_checkpoint import config_from_json
from connectome_fighter.valence_plasticity import load_state

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--source-archive',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout-seconds',type=int,default=1500)
    p.add_argument('--resume-dir',type=Path)
    args=p.parse_args()
    if os.environ.get('CI')!='true' or os.environ.get('VERCEL'):p.error('standalone CI only')
    if not 120<=args.timeout_seconds<=1800:p.error('invalid bounded timeout')
    runtime=args.runtime_root.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();deadline=start+args.timeout_seconds
    manifest=json.loads((runtime/'manifest.json').read_text())
    if manifest['canonical_model']!='MaleCNS v1.0 + pinned Shiu LIF' or manifest['policy_pixel_access'] is not False or manifest['learning_enabled'] is not False:raise ValueError('runtime boundary mismatch')
    ref=runtime/(runtime/'runtime/python310.path').read_text().strip()
    if str(ref)!=manifest['brian2_expected_sys_executable'] or manifest['brian2_compilerless_reuse_verified'] is not True:raise ValueError('runtime path/cache mismatch')
    for name,key in [('data/malecns-shiu-strict-v1/connectivity.parquet','adapter_connectivity_sha256'),('shiu/model.py','shiu_model_sha256'),('fightingice/FightingICE.jar','fightingice_jar_sha256')]:
        if sha(runtime/name)!=manifest[key]:raise ValueError('runtime asset mismatch: '+name)
    interface=json.loads((runtime/'data/interface.json').read_text());embedded=interface.pop('interface_sha256')
    if hashlib.sha256(json.dumps(interface,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=embedded or embedded!=manifest['interface_sha256']:raise ValueError('interface hash mismatch')
    if interface['decision']['window_ms']!=20:raise ValueError('unexpected neural clock')
    for name in ['src','scripts','configs']:
        shutil.copytree(ROOT/name,runtime/'repo'/name,dirs_exist_ok=True)
    base=runtime/'data/malecns-shiu-strict-v1'
    candidate_path=runtime/'data/malecns-valence-v1/kc_mbon_valence_candidates.parquet'
    c=pd.read_parquet(candidate_path).sort_values('synapse_index').reset_index(drop=True)
    if c.empty or not (c['sign']==1).all():raise ValueError('invalid audited candidate edges')
    source=out/'source';source.mkdir(exist_ok=False)
    with tarfile.open(args.source_archive) as archive:archive.extractall(source,filter='data')
    state_path=source/'state/GARNET.npz'
    cfg=config_from_json(json.loads((ROOT/'configs/plasticity_combat_v1.json').read_text()))
    state=load_state(state_path,expected_character='GARNET',n_candidates=len(c),expected_candidate_sha256=sha(candidate_path),config=cfg)
    parent_meta=json.loads(state_path.with_suffix('.npz.json').read_text())
    parent_sha=sha(state_path)
    membership=group_indices(c['synapse_index'].to_numpy(dtype=np.int64),8)
    np.savez_compressed(out/'group-membership.npz',synapse_index=c['synapse_index'].to_numpy(),group=membership)
    runtime_identity={k:manifest[k] for k in ['adapter_connectivity_sha256','shiu_model_sha256','fightingice_jar_sha256','interface_sha256']}
    if json.loads((ROOT/'configs/paired_training_v1.json').read_text()) != CONFIG:
        raise ValueError('configuration changed without a protocol version')
    parent={'cycle':0,'accepted_updates':0,'total_completed_games':0,
            'weights_sha256':weights_sha(state.multipliers),'state_file_sha256':None}
    origin=state.multipliers.copy();theta=np.zeros(CONFIG['groups']);history=[]
    seed_parent=parent_meta
    if args.resume_dir:
        latest=json.loads((args.resume_dir/'latest.json').read_text())
        parent=latest['state']
        origin,theta=load_search(args.resume_dir/'search-state.npz',parent,sha(candidate_path),membership,runtime_identity)
        seed_parent=parent['seed_parent'];history=latest.get('history',[])
    cycle=parent['cycle']+1;seeds=cycle_seeds(cycle);sigma=CONFIG['sigma']
    directions=np.random.default_rng(seeds['directions']).normal(size=(CONFIG['pairs_per_cycle'],CONFIG['groups']))
    design={'experiment':EXPERIMENT,'config':CONFIG,'config_sha256':digest(CONFIG),'cycle':cycle,
            'parent':parent,'seed_parent':seed_parent,'tested_checkout':os.environ.get('GITHUB_SHA'),
            'runtime_manifest':manifest,'numpy_version':np.__version__,'python':sys.version,
            'paired_directions':directions.tolist(),'center':theta.tolist(),'seeds':seeds,
            'group_membership_sha256':sha(out/'group-membership.npz'),
            'candidate_only':True,'auto_promotion':False,'scheduled':os.environ.get('GITHUB_EVENT_NAME')=='schedule',
            'training_opponent':'explicit neutral dummy','combat_opponent':'ZEN canonical baseline',
            'interpretation_boundary':'Training gains are not held-out fighting strength. No artificial graph or P1 game heuristic.',
            'started_at':datetime.now(timezone.utc).isoformat()}
    write(out/'design.json',design)
    wrapper=out/'reference-python'
    wrapper.write_text('#!/bin/sh\nexport PYTHONPATH='+shlex.quote(str(runtime/'runtime/site310'))+'\nexec '+shlex.quote(str(ref))+' "$@"\n');wrapper.chmod(0o755)
    env=dict(os.environ,PATH=f"{runtime/'runtime/jre21/bin'}:{os.environ['PATH']}",
             PYTHONPATH=f"{ROOT/'src'}:{runtime/'runtime/site311'}",OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    matches=[]
    def game(name,params,opponent,seed,video=False):
        values=multipliers(origin,params,membership)
        weight_hash=hashlib.sha256(values.tobytes()).hexdigest()
        # Every sign is executed even if clipped parameters coincide; repeated
        # baseline is also executed to detect sampled determinism problems.
        adapter=out/'adapters'/name;adapter.parent.mkdir(exist_ok=True)
        conn_sha=materialize(base,c,values,adapter,{'parent_sha256':parent['weights_sha256'],'theta':params.tolist(),'multipliers_sha256':weight_hash})
        with (out/(name+'-game.log')).open('wb') as handle:
            proc=subprocess.Popen(['java','-cp','FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*','Main','--headless-mode','--pyftg-mode','--input-sync','--limithp','400','400','--port','31415','-r','1','-f','3600'],cwd=runtime/'fightingice',env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                for _ in range(120):
                    if proc.poll() is not None:raise RuntimeError('game failed to start')
                    if 'Socket server is started' in (out/(name+'-game.log')).read_text(errors='replace'):break
                    if time.monotonic()>deadline:raise TimeoutError('overall budget exhausted')
                    time.sleep(.25)
                else:raise TimeoutError('game startup')
                cmd=[sys.executable,ROOT/'scripts/paired_search_game.py','--runtime-root',runtime,'--adapter',adapter,'--reference-python',wrapper,'--seed',str(seed),'--opponent',opponent,'--out',out/'matches'/name,'--timeout',str(max(1,min(300,int(deadline-time.monotonic()))))]
                if video:cmd+=['--video']
                with (out/(name+'-runner.log')).open('wb') as log:
                    runner=subprocess.Popen([str(x) for x in cmd],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:
                        code=runner.wait(timeout=max(1,deadline-time.monotonic()))
                        if code:raise RuntimeError(f'{name} failed ({code}); inspect runner log')
                    finally:stop(runner)
            finally:stop(proc)
        result=json.loads((out/'matches'/name/'result.json').read_text())
        if result['status']!='PASS' or sha(adapter/'connectivity.parquet')!=conn_sha or sha(state_path)!=parent_sha:raise ValueError('round or frozen-weight audit failed')
        entry={'name':name,'opponent':opponent,'seed':seed,'theta':params.tolist(),
               'multipliers_sha256':weight_hash,'connectivity_sha256':conn_sha,'metrics':result['metrics']}
        if video:
            path=out/'matches'/name/'screen.mp4'
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
            stream=next(v for v in probe['streams'] if v['codec_type']=='video')
            if (stream['width'],stream['height'])!=(960,640) or stream['codec_name']!='h264':raise ValueError('unexpected official video')
            entry['video']={'path':str(path.relative_to(out)),'sha256':sha(path),'bytes':path.stat().st_size,'recording_seconds':float(probe['format']['duration']),'game_elapsed_frames':result['metrics']['elapsed_frame']}
        matches.append(entry);write(out/'matches-summary.json',matches)
        shutil.rmtree(adapter)  # bound disk use; multiplier design and hashes persist
        print(json.dumps({'completed':name,'metrics':entry['metrics']}),flush=True)
        return entry
    result={'status':'FAIL','experiment':EXPERIMENT}
    try:
        before=game('curriculum-before',theta,'neutral',seeds['training'],video=True)
        repeat=game('curriculum-repeat',theta,'neutral',seeds['training'])
        repeatable=before['metrics']==repeat['metrics']
        write(out/'baseline-repeatability.json',{'identical_metrics':repeatable})
        if not repeatable:raise RuntimeError('same-seed baseline not repeatable: cannot attribute paired changes')
        plus=[];minus=[]
        for j,u in enumerate(directions):
            # Alternate execution order to avoid a fixed plus-first bias.
            local={}
            for sign in ([1,-1] if j%2==0 else [-1,1]):
                name=f'probe-{j}-'+('plus' if sign==1 else 'minus')
                e=game(name,theta+sign*sigma*u,'neutral',seeds['training'])
                local[sign]=e['metrics']['curriculum_score']
            plus.append(local[1]);minus.append(local[-1])
        gradient,step=propose(directions,plus,minus,sigma=sigma,learning_rate=CONFIG['learning_rate'],max_step=CONFIG['max_step'])
        accepted=False;selected=theta;proposal_result=None
        if np.any(step):
            proposal_result=game('curriculum-proposal',theta+step,'neutral',seeds['training'],video=True)
            accepted=proposal_result['metrics']['curriculum_score']>before['metrics']['curriculum_score']+1e-12
            if accepted:selected=theta+step
        curriculum_validation=[]
        if accepted:
            for seed in seeds['confirmation']:
                a=game(f'validation-{seed}-parent',theta,'neutral',seed)
                b=game(f'validation-{seed}-candidate',selected,'neutral',seed)
                curriculum_validation.append({'seed':seed,'parent':a['metrics'],'candidate':b['metrics']})
        if accepted and (not confirmation_pass(curriculum_validation)
            or np.array_equal(multipliers(origin,selected,membership),multipliers(origin,theta,membership))):
            accepted=False;selected=theta
        combat_before=game('combat-before',theta,'canonical',seeds['combat'],video=True)
        combat_after=game('combat-after',selected,'canonical',seeds['combat'],video=True)
        checkpoint=out/'candidate';checkpoint.mkdir()
        child_meta=save_search(checkpoint/'search-state.npz',origin=origin,theta=selected,membership=membership,
            parent=parent,runtime_identity=runtime_identity,candidate_sha=sha(candidate_path),
            completed_games=len(matches),accepted=accepted,cycle=cycle,seed_parent=seed_parent)
        reason='confirmed curriculum gain' if accepted else 'zero paired signal' if not np.any(step) else 'proposal not confirmed'
        result={'status':'PASS','experiment':EXPERIMENT,'cycle':cycle,'config':CONFIG,
                'source_commit':os.environ.get('GITHUB_SHA'),'source_run_id':os.environ.get('GITHUB_RUN_ID'),
                'source_run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT','1'),
                'source_event':os.environ.get('GITHUB_EVENT_NAME'),'completed_at':datetime.now(timezone.utc).isoformat(),
                'accepted_update':accepted,'update_reason':reason,'state':child_meta,
                'plus_scores':plus,'minus_scores':minus,'gradient':gradient.tolist(),'proposal_step':step.tolist(),
                'baseline_curriculum':before['metrics'],'proposal_curriculum':proposal_result['metrics'] if proposal_result else None,
                'curriculum_validation':curriculum_validation,'combat_before':combat_before['metrics'],'combat_after':combat_after['metrics'],
                'parent_source_unchanged':sha(state_path)==parent_sha,'actual_pipeline_seconds':time.monotonic()-start,
                'completed_games':len(matches),'seeds':seeds,'strength_claim':False,'auto_promotion':False,'candidate_only':True,
                'schedule_minutes':CONFIG['schedule_minutes'],'config_sha256':digest(CONFIG),
                'interpretation_boundary':'Completed real games. Curriculum gains are not evidence of competitive strength. Recordings are not LIVE.'}
        record={k:result[k] for k in ['cycle','completed_at','accepted_update','update_reason','completed_games','source_run_id']}
        record.update(accepted_updates=child_meta['accepted_updates'],weights_sha256=child_meta['weights_sha256'],
                      curriculum_score=before['metrics']['curriculum_score'],combat_score=combat_after['metrics']['combat_score'],
                      damage_dealt_hp=combat_after['metrics']['damage_dealt_hp'])
        result['history']=(history+[record])[-30:]
        export=out/'export';export.mkdir()
        shutil.copy2(checkpoint/'search-state.npz',export/'search-state.npz')
        shutil.copy2(checkpoint/'search-state.json',export/'search-state.json')
        result['videos']={}
        for key,entry in [('curriculum',before),('before',combat_before),('after',combat_after)]:
            src=out/entry['video']['path'];name=key+'.mp4';shutil.copy2(src,export/name)
            result['videos'][key]={**entry['video'],'path':name}
        write(export/'summary.json',result);write(out/'result.json',result)
        return 0
    except Exception:
        result.update(error=traceback.format_exc(),completed_games=len(matches),actual_pipeline_seconds=time.monotonic()-start)
        write(out/'result.json',result);raise

if __name__=='__main__':raise SystemExit(main())
