#!/usr/bin/env python3
"""Bounded actual-game paired search with optional persistent candidate state.

Run under bundled bridge Python/site311. P1 remains neural; the dummy curriculum
is separate from canonical combat. This process does not publish or promote.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import traceback

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from connectome_fighter.paired_search import EXPERIMENT, group_indices, multipliers, propose
from connectome_fighter.combat_checkpoint import config_from_json
from connectome_fighter.valence_plasticity import load_state
from connectome_fighter.paired_rollout import (ROLLOUT, PROTOCOL_SHA256, load_parent,
    save_checkpoint, seeds, weights_hash)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')


def stop(proc):
    try:os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait(timeout=5)


def materialize(base, candidates, values, dest, identity):
    """Scale only verified existing positive candidate rows; use float64 runtime weights."""
    dest.mkdir(parents=True,exist_ok=False)
    for name in ['completeness.csv','neuron_metadata.parquet']:
        shutil.copy2(base/name,dest/name)
    indices=candidates['synapse_index'].to_numpy(dtype=np.int64)
    if not np.all(indices[1:]>indices[:-1]) or np.any(indices<0):raise ValueError('invalid candidate order')
    pre=candidates['pre_index'].to_numpy(dtype=np.int64);post=candidates['post_index'].to_numpy(dtype=np.int64)
    source=pq.ParquetFile(base/'connectivity.parquet')
    column=source.schema_arrow.get_field_index('Excitatory x Connectivity')
    if column<0:raise ValueError('weight column missing')
    values=np.asarray(values,dtype=np.float64)
    if values.shape!=(len(indices),) or not np.isfinite(values).all() or np.any(values<.8-1e-7) or np.any(values>1):raise ValueError('invalid effective multipliers')
    # The structural source column is int64. Never truncate learned weights.
    schema=source.schema_arrow.set(column,pa.field('Excitatory x Connectivity',pa.float64()))
    offset=0;visited=0
    with pq.ParquetWriter(dest/'connectivity.parquet',schema,compression='zstd') as writer:
        for batch in source.iter_batches(batch_size=250000):
            table=pa.Table.from_batches([batch]);end=offset+len(table)
            lo,hi=np.searchsorted(indices,[offset,end])
            weights=table.column(column).to_numpy().astype(np.float64,copy=True)
            if hi>lo:
                local=indices[lo:hi]-offset
                if not np.array_equal(table['Presynaptic_Index'].to_numpy()[local],pre[lo:hi]) or not np.array_equal(table['Postsynaptic_Index'].to_numpy()[local],post[lo:hi]):raise ValueError('candidate identity mismatch')
                if np.any(weights[local]<=0):raise ValueError('candidate sign mismatch')
                weights[local]*=values[lo:hi]
                visited+=hi-lo
            table=table.set_column(column,schema.field(column),pa.array(weights,type=pa.float64()))
            writer.write_table(table);offset=end
    if visited!=len(indices):raise ValueError('not all candidate rows visited')
    actual=pq.read_table(dest/'connectivity.parquet',columns=['Excitatory x Connectivity']).column(0).to_numpy()
    original=pq.read_table(base/'connectivity.parquet',columns=['Excitatory x Connectivity']).column(0).to_numpy().astype(np.float64)
    expected=original.copy();expected[indices]*=values
    if not np.array_equal(actual,expected) or not np.array_equal(np.sign(actual),np.sign(original)):raise ValueError('materialized float weights or signs changed unexpectedly')
    manifest=json.loads((base/'manifest.json').read_text())
    manifest['adapter']+='+'+EXPERIMENT
    manifest['output_hashes']['connectivity_sha256']=sha(dest/'connectivity.parquet')
    manifest['experimental_search']=dict(identity,experiment=EXPERIMENT,only_existing_KC_MBON_edges=True,
        sign_changed=False,topology_changed=False,policy_frozen_during_round=True)
    write(dest/'manifest.json',manifest)
    return manifest['output_hashes']['connectivity_sha256']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--source-archive',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout-seconds',type=int,default=1500)
    p.add_argument('--persistent',action='store_true',help='Explicit versioned recurring lane; not approved inference')
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
    membership=group_indices(c['synapse_index'].to_numpy(dtype=np.int64),8)
    if args.persistent:
        state=load_parent(source,sha(candidate_path),membership,cfg)
        state_path=state.state_path
        parent_meta=state.metadata
        cycle=parent_meta['cycle_index']+1
        seed_plan=seeds(cycle)
        phase=parent_meta['next_phase']
    else:
        state=load_state(state_path,expected_character='GARNET',n_candidates=len(c),expected_candidate_sha256=sha(candidate_path),config=cfg)
        parent_meta=json.loads(state_path.with_suffix('.npz.json').read_text())
        cycle=None
        seed_plan={'direction':926015,'training':910001,'selection':910001,'validation':[910101,910102],'combat':800101}
        phase='curriculum'
    if args.persistent:
        substrate={'anatomy':manifest['adapter_connectivity_sha256'], 'reference':manifest['shiu_model_sha256'],
                   'game':manifest['fightingice_jar_sha256'], 'interface':embedded,
                   'worker':sha(ROOT/'scripts/malecns_lif_worker.py'),
                   'session':sha(ROOT/'src/connectome_fighter/session.py'),
                   'contracts':sha(ROOT/'src/connectome_fighter/contracts.py'),
                   'observations':sha(ROOT/'src/connectome_fighter/observations.py')}
        if cycle>1 and parent_meta.get('substrate')!=substrate:
            raise ValueError('numerical/biological substrate changed; explicit new lineage required')
        state.metadata=dict(state.metadata,substrate=substrate)
        parent_meta=state.metadata
    parent_sha=sha(state_path)
    training_opponent='neutral' if phase=='curriculum' else 'canonical'
    score_key='curriculum_score' if phase=='curriculum' else 'combat_score'
    np.savez_compressed(out/'group-membership.npz',synapse_index=c['synapse_index'].to_numpy(),group=membership)
    theta=np.zeros(8);sigma=.04;rng=np.random.default_rng(seed_plan['direction'])
    directions=rng.normal(size=(4,8))
    design={'experiment':EXPERIMENT,'parent':parent_meta,'tested_checkout':os.environ.get('GITHUB_SHA'),
            'runtime_manifest':manifest,'numpy_version':np.__version__,'python':sys.version,
            'paired_directions':directions.tolist(),'sigma':sigma,'learning_rate':.05,'step_norm_cap':.02,
            'groups':8,'group_membership_sha256':sha(out/'group-membership.npz'),
            'multiplier_bounds':[.8,1.0],'training_seed':seed_plan['training'],'validation_seeds':seed_plan['validation'],
            'decision_interval_frames':60,'neural_window_ms':20,'round_frame_limit':3600,
            'candidate_only':True,'auto_promotion':False,'scheduled':bool(args.persistent),
            'rollout':ROLLOUT if args.persistent else None,'protocol_sha256':PROTOCOL_SHA256 if args.persistent else None,
            'phase':phase,'cycle_index':cycle,'seed_plan':seed_plan,
            'training_opponent':training_opponent,'combat_opponent':'ZEN canonical baseline',
            'interpretation_boundary':'Engineering search on existing anatomy, not an endogenous plasticity mechanism. No held-out strength claim from this pilot.',
            'started_at':datetime.now(timezone.utc).isoformat()}
    write(out/'design.json',design)
    wrapper=out/'reference-python'
    wrapper.write_text('#!/bin/sh\nexport PYTHONPATH='+shlex.quote(str(runtime/'runtime/site310'))+'\nexec '+shlex.quote(str(ref))+' "$@"\n');wrapper.chmod(0o755)
    env=dict(os.environ,PATH=f"{runtime/'runtime/jre21/bin'}:{os.environ['PATH']}",
             PYTHONPATH=f"{ROOT/'src'}:{runtime/'runtime/site311'}",OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    matches=[]
    def game(name,params,opponent,seed,video=False):
        values=multipliers(state.multipliers,params,membership)
        weight_hash=hashlib.sha256(values.tobytes()).hexdigest()
        # Every sign is executed even if clipped parameters coincide; repeated
        # baseline is also executed to detect sampled determinism problems.
        adapter=out/'adapters'/name;adapter.parent.mkdir(exist_ok=True)
        conn_sha=materialize(base,c,values,adapter,{'parent_sha256':parent_sha,'theta':params.tolist(),'multipliers_sha256':weight_hash})
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
        before=game('curriculum-before',theta,training_opponent,seed_plan['training'],video=True)
        repeat=game('curriculum-repeat',theta,training_opponent,seed_plan['training'])
        repeatable=before['metrics']==repeat['metrics']
        write(out/'baseline-repeatability.json',{'identical_metrics':repeatable})
        if not repeatable:raise RuntimeError('same-seed baseline not repeatable: cannot attribute paired changes')
        plus=[];minus=[]
        for j,u in enumerate(directions):
            # Alternate execution order to avoid a fixed plus-first bias.
            local={}
            for sign in ([1,-1] if j%2==0 else [-1,1]):
                name=f'probe-{j}-'+('plus' if sign==1 else 'minus')
                e=game(name,sign*sigma*u,training_opponent,seed_plan['training'])
                local[sign]=e['metrics'][score_key]
            plus.append(local[1]);minus.append(local[-1])
        gradient,step=propose(directions,plus,minus,sigma=sigma)
        accepted=False;selected=theta;proposal_result=None
        if np.any(step):
            selection_parent=(game('selection-parent',theta,training_opponent,seed_plan['selection']) if args.persistent else before)
            proposal_result=game('curriculum-proposal',step,training_opponent,seed_plan['selection'],video=True)
            accepted=proposal_result['metrics'][score_key]>selection_parent['metrics'][score_key]+1e-12
            if phase=='curriculum':
                accepted=accepted and proposal_result['metrics']['damage_dealt_hp']>=selection_parent['metrics']['damage_dealt_hp']
            accepted=bool(accepted and not np.array_equal(multipliers(state.multipliers,step,membership),state.multipliers))
            if accepted:selected=step
        curriculum_validation=[]
        if accepted:
            for seed in seed_plan['validation']:
                a=game(f'validation-{seed}-parent',theta,training_opponent,seed)
                b=game(f'validation-{seed}-candidate',selected,training_opponent,seed)
                curriculum_validation.append({'seed':seed,'parent':a['metrics'],'candidate':b['metrics']})
        combat_before=game('combat-before',theta,'canonical',800101,video=True)
        combat_after=game('combat-after',selected,'canonical',800101,video=True)
        checkpoint=out/'candidate'
        if args.persistent:
            child_meta=save_checkpoint(checkpoint,state,membership,multipliers(state.multipliers,selected,membership),
                accepted,sha(candidate_path),curriculum_validation,phase)
        else:
            checkpoint=out/'candidate';checkpoint.mkdir()
            np.savez_compressed(checkpoint/'search-state.npz',theta=selected,multipliers=multipliers(state.multipliers,selected,membership),membership=membership,parent_multipliers=state.multipliers)
            child_meta={'experiment':EXPERIMENT,'model':'bounded-group-perturbation-on-existing-KC-MBON-v1',
                        'parent_state_sha256':parent_sha,'parent_generation':state.generation,
                        'accepted_update_count':int(accepted),'weights_changed':bool(accepted),
                        'state_file_sha256':sha(checkpoint/'search-state.npz'),'candidate_sha256':sha(candidate_path),
                        'candidate_only':True,'auto_promotion':False,'production_compatible':False}
            write(checkpoint/'search-state.json',child_meta)
        result={'status':'PASS','experiment':EXPERIMENT,'parent':parent_meta,'accepted_update':accepted,
                'phase':phase,'cycle_index':cycle,'rollout':ROLLOUT if args.persistent else None,
                'parent_weights_sha256':weights_hash(state.multipliers),
                'update_reason':'strict independent-seed score gain' if accepted and args.persistent else 'strict curriculum gain' if accepted else 'zero paired signal' if not np.any(step) else 'proposal did not outperform parent',
                'plus_scores':plus,'minus_scores':minus,'gradient':gradient.tolist(),'proposal_step':step.tolist(),
                'baseline_curriculum':before['metrics'],'proposal_curriculum':proposal_result['metrics'] if proposal_result else None,
                'curriculum_validation':curriculum_validation,'combat_before':combat_before['metrics'],'combat_after':combat_after['metrics'],
                'parent_source_unchanged':sha(state_path)==parent_sha,'actual_pipeline_seconds':time.monotonic()-start,
                'completed_games':len(matches),'checkpoint':child_meta,'strength_claim':False}
        write(out/'result.json',result)
        return 0
    except Exception:
        result.update(error=traceback.format_exc(),completed_games=len(matches),actual_pipeline_seconds=time.monotonic()-start)
        write(out/'result.json',result);raise

if __name__=='__main__':raise SystemExit(main())
