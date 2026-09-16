#!/usr/bin/env python3
"""Read-only actual-game comparison of neural output readout rules.

The current candidate checkpoint, anatomy, recurrent weights, Shiu dynamics,
observation mapping, seed, interface and 60-frame action cadence are fixed. Only
how the seven existing output-group spike counts are converted to a game action
changes. Experimental residual readouts use neural history only, never game
coordinates/HP/action state. No training or checkpoint mutation occurs.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tarfile
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
MODES=('canonical','delta','ema-residual')


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path:Path,value)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')


def stop(proc:subprocess.Popen)->None:
    if proc.poll() is not None:return
    try:os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait(timeout=5)


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--source-archive',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout-seconds',type=int,default=1500)
    args=p.parse_args()
    if os.environ.get('CI')!='true' or os.environ.get('VERCEL'):p.error('standalone CI only')
    if not 300<=args.timeout_seconds<=1800:p.error('timeout must be 300..1800 seconds')
    runtime=args.runtime_root.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();deadline=started+args.timeout_seconds
    result={'status':'FAIL','kind':'temporal-neural-readout-sensitivity-v1','strength_claim':False}
    try:
        manifest=json.loads((runtime/'manifest.json').read_text(encoding='utf-8'))
        if manifest['canonical_model']!='MaleCNS v1.0 + pinned Shiu LIF' or manifest['learning_enabled'] is not False or manifest['policy_pixel_access'] is not False:
            raise ValueError('runtime boundary mismatch')
        interface=json.loads((runtime/'data/interface.json').read_text(encoding='utf-8'))
        if float(interface['decision']['window_ms'])!=20.0:raise ValueError('neural decision window changed')
        ref=runtime/(runtime/'runtime/python310.path').read_text().strip()
        bridge=runtime/(runtime/'runtime/python311.path').read_text().strip()
        source=out/'source';source.mkdir()
        with tarfile.open(args.source_archive) as archive:archive.extractall(source,filter='data')
        state=source/'state/GARNET.npz';meta=json.loads(state.with_suffix('.npz.json').read_text())
        if sha(state)!=meta['state_sha256'] or meta['character']!='GARNET' or meta['reward_id']!='R2e-combat-v1':
            raise ValueError('candidate checkpoint identity mismatch')
        parent_sha=sha(state)
        adapter=out/'candidate-adapter'
        env=dict(os.environ,PYTHONPATH=f"{ROOT/'src'}:{runtime/'runtime/site311'}",
                 PATH=f"{runtime/'runtime/jre21/bin'}:{os.environ['PATH']}",
                 OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        wrapper=out/'reference-python'
        wrapper.write_text('#!/bin/sh\nexport PYTHONPATH='+shlex.quote(str(runtime/'runtime/site310'))+'\nexec '+shlex.quote(str(ref))+' "$@"\n',encoding='utf-8');wrapper.chmod(0o755)
        subprocess.run([str(bridge),str(ROOT/'scripts/materialize_malecns_valence_adapter.py'),
            '--base-adapter',str(runtime/'data/malecns-shiu-strict-v1'),
            '--candidates',str(runtime/'data/malecns-valence-v1/kc_mbon_valence_candidates.parquet'),
            '--state',str(state),'--character','GARNET','--plasticity-config',str(ROOT/'configs/plasticity_combat_v1.json'),
            '--out',str(adapter)],check=True,env=env,cwd=ROOT,timeout=180)
        if sha(state)!=parent_sha:raise RuntimeError('materialization changed source state')
        rows=[]
        for opponent in ('neutral','canonical'):
            seed=940001 if opponent=='neutral' else 800101
            for mode in MODES:
                if time.monotonic()>deadline:raise TimeoutError('overall readout experiment budget exhausted')
                name=f'{opponent}-{mode}'
                folder=out/'matches'/name
                game_log=out/(name+'-game.log')
                with game_log.open('wb') as handle:
                    game=subprocess.Popen([str(runtime/'runtime/jre21/bin/java'),'-cp','FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*','Main','--headless-mode','--pyftg-mode','--input-sync','--limithp','400','400','--port','31415','-r','1','-f','3600'],cwd=runtime/'fightingice',env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    for _ in range(120):
                        if game.poll() is not None:raise RuntimeError(f'{name}: FightingICE exited before startup')
                        if 'Socket server is started' in game_log.read_text(errors='replace'):break
                        time.sleep(.25)
                    else:raise TimeoutError(f'{name}: FightingICE startup timeout')
                    command=[str(bridge),str(ROOT/'scripts/paired_search_game.py'),'--runtime-root',str(runtime),'--adapter',str(adapter),'--reference-python',str(wrapper),'--out',str(folder),'--seed',str(seed),'--opponent',opponent,'--decision-interval','60','--readout-mode',mode,'--timeout',str(max(1,min(360,int(deadline-time.monotonic()))))]
                    if opponent=='canonical':command+=['--video']
                    subprocess.run(command,check=True,env=env,cwd=ROOT,timeout=max(1,deadline-time.monotonic()))
                finally:stop(game)
                one=json.loads((folder/'result.json').read_text(encoding='utf-8'))
                if one['status']!='PASS' or one['decision_interval_frames']!=60 or one['p1_readout_mode']!=mode or one['p1_readout_uses_game_state'] is not False or one['learning_performed'] is not False:
                    raise RuntimeError(f'{name}: invalid completed result')
                row={'opponent':opponent,'readout_mode':mode,'seed':seed,'metrics':one['metrics'],
                     'p1_action_histogram':one['audit']['action_histograms'][0],
                     'workers':one['workers'],'source_state_sha256':parent_sha}
                if opponent=='canonical':
                    video=folder/'screen.mp4';row['video']={'sha256':sha(video),'bytes':video.stat().st_size,'relative_path':str(video.relative_to(out))}
                rows.append(row);write(out/'partial-results.json',rows)
                if sha(state)!=parent_sha:raise RuntimeError('readout run changed candidate state')
        by_opponent={kind:[r for r in rows if r['opponent']==kind] for kind in ('neutral','canonical')}
        result={'status':'PASS','kind':'temporal-neural-readout-sensitivity-v1','candidate_generation':int(meta['generation']),
                'candidate_state_sha256':parent_sha,'reward_id':meta['reward_id'],'tested_at':datetime.now(timezone.utc).isoformat(),
                'decision_interval_frames':60,'fixed_neural_window_ms':20.0,'modes':list(MODES),
                'canonical_interface_sha256':interface['interface_sha256'],'learning_performed':False,'weights_changed':False,
                'readout_game_state_used':False,'policy_pixel_access':False,'synthetic_neural_fixture':False,
                'results':by_opponent,'actual_pipeline_seconds':time.monotonic()-started,'strength_claim':False,
                'interpretation_boundary':'Only the project-defined conversion from existing neural output-group counts to a game action changes. Residual modes use neural history only. This is interface engineering, not biological motor semantics or learning evidence.'}
        write(out/'result.json',result)
        return 0
    except Exception:
        result['error']=traceback.format_exc();result['actual_pipeline_seconds']=time.monotonic()-started
        write(out/'result.json',result);raise

if __name__=='__main__':raise SystemExit(main())
