#!/usr/bin/env python3
"""Independent no-learning holdout comparison for two archived combat candidates."""
from __future__ import annotations
import argparse, hashlib, json, os, shlex, signal, subprocess, sys, tarfile, time
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
READOUT_MODE='ema-residual'
READOUT_CONTRACT='malecns-temporal-readout-v1'
MATCH_STATUS='COMPLETED_WITH_VALIDATED_EXPERIMENTAL_READOUT_TRACES'
# Intentionally distinct from training seeds, the legacy replay anchor, and the
# fixed candidate-selection validation suite. Once reported, these are evidence,
# not reusable "fresh" holdouts for future model selection.
HOLDOUT_SUITE=(
    {'case_id':'zen-independent-h1','opponent':'ZEN','seed_p1':820111,'seed_p2':32011},
    {'case_id':'zen-independent-h2','opponent':'ZEN','seed_p1':820112,'seed_p2':32012},
    {'case_id':'lud-independent-h1','opponent':'LUD','seed_p1':820211,'seed_p2':32021},
    {'case_id':'lud-independent-h2','opponent':'LUD','seed_p1':820212,'seed_p2':32022},
    {'case_id':'nez-independent-h1','opponent':'NEZ','seed_p1':820311,'seed_p2':32031},
    {'case_id':'nez-independent-h2','opponent':'NEZ','seed_p1':820312,'seed_p2':32032},
)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
    return h.hexdigest()

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')

def stop(proc):
    if proc.poll() is not None:return
    try: os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=5)
    except (ProcessLookupError,subprocess.TimeoutExpired):
        try: os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
        except ProcessLookupError: pass

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--candidate',action='append',nargs=2,metavar=('LABEL','ARCHIVE'),required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout-seconds',type=int,default=1200)
    args=p.parse_args()
    if os.environ.get('CI')!='true' or os.environ.get('VERCEL'):p.error('standalone CI only')
    runtime=args.runtime_root.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+args.timeout_seconds
    manifest=json.loads((runtime/'manifest.json').read_text())
    assert manifest['canonical_model']=='MaleCNS v1.0 + pinned Shiu LIF'
    assert manifest['learning_enabled'] is False and manifest['policy_pixel_access'] is False
    ref=runtime/(runtime/'runtime/python310.path').read_text().strip()
    bridge=runtime/(runtime/'runtime/python311.path').read_text().strip()
    env=dict(os.environ,PYTHONPATH=f"{runtime/'repo/src'}:{runtime/'runtime/site311'}",
             PATH=f"{runtime/'runtime/jre21/bin'}:{os.environ['PATH']}",
             OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    wrapper=out/'reference-python'
    wrapper.write_text('#!/bin/sh\nexport PYTHONPATH='+shlex.quote(str(runtime/'runtime/site310'))+'\nexec '+shlex.quote(str(ref))+' "$@"\n');wrapper.chmod(0o755)
    def run(cmd,name):
        with (out/(name+'.log')).open('wb') as log:
            proc=subprocess.Popen([str(x) for x in cmd],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                rc=proc.wait(timeout=max(1,deadline-time.monotonic()))
                if rc:raise RuntimeError(f'{name} exited {rc}; see log')
            finally:stop(proc)
    base=runtime/'data/malecns-shiu-strict-v1'
    candidates=runtime/'data/malecns-valence-v1/kc_mbon_valence_candidates.parquet'
    cfg=ROOT/'configs/plasticity_combat_v1.json'
    adapters={}
    identities={}
    for label,archive in args.candidate:
        package=out/f'package-{label}';package.mkdir()
        with tarfile.open(archive) as tar:tar.extractall(package,filter='data')
        state=package/'state/GARNET.npz';meta=json.loads(state.with_suffix('.npz.json').read_text())
        assert sha(state)==meta['state_sha256'] and meta['character']=='GARNET'
        assert meta['reward_id']=='R2e-combat-v1' and meta['model']=='KC-MBON-valence-depression-v0'
        adapter=out/f'adapter-{label}'
        run([bridge,runtime/'repo/scripts/materialize_malecns_valence_adapter.py','--base-adapter',base,'--candidates',candidates,
             '--state',state,'--character','GARNET','--plasticity-config',cfg,'--out',adapter],f'materialize-{label}')
        adapters[label]=adapter
        identities[label]={'generation':int(meta['generation']),'state_sha256':meta['state_sha256'],'archive_sha256':sha(archive)}
    def match(label,case,adapter):
        name=f"{label}-{case['case_id']}";game_dir=runtime/'fightingice'
        with (out/(name+'-game.log')).open('wb') as log:
            game=subprocess.Popen(['java','-cp','FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*',
              'Main','--headless-mode','--pyftg-mode','--input-sync','--limithp','400','400','--port','31415','-r','1','-f','3600'],
              cwd=game_dir,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                for _ in range(90):
                    if game.poll() is not None:raise RuntimeError('game exited before startup')
                    if 'Socket server is started' in (out/(name+'-game.log')).read_text(errors='replace'):break
                    time.sleep(.5)
                else:raise TimeoutError('game startup timeout')
                cmd=[bridge,runtime/'repo/scripts/run_game_malecns_lif.py','--host','127.0.0.1','--port','31415',
                  '--character-p1','GARNET','--character-p2',case['opponent'],'--seed-p1',str(case['seed_p1']),'--seed-p2',str(case['seed_p2']),
                  '--reference-python',wrapper,'--reference-model',runtime/'shiu/model.py','--adapter-dir',base,'--adapter-dir-p1',adapter,
                  '--interface',runtime/'data/interface.json','--decision-interval','60','--readout-mode-p1',READOUT_MODE,'--readout-mode-p2','canonical',
                  '--games','1','--expected-rounds','1','--timeout',str(max(1,min(600,int(deadline-time.monotonic())))),
                  '--run-id',name,'--out',out/'matches']
                run(cmd,name)
            finally:stop(game)
        folder=out/'matches'/name;status=json.loads((folder/'status.json').read_text())
        assert status['status']==MATCH_STATUS and status['learning_performed'] is False and status['trace_trainable'] is False
        assert status['readout_modes']==[READOUT_MODE,'canonical'] and status['readout_game_state_used'] is False
        rows=[json.loads(x) for x in (folder/'p1.jsonl').read_text().splitlines() if x.strip()]
        assert len(rows)==1 and rows[0]['terminated'] is True and rows[0]['truncated'] is False
        trace=rows[0];hps=[max(0,v) for v in trace['remaining_hps']];initial=trace['transitions'][0]['display']
        return {'winner':'GARNET' if hps[0]>hps[1] else case['opponent'] if hps[0]<hps[1] else 'DRAW',
          'p1_hp':hps[0],'p2_hp':hps[1],'damage_dealt_hp':max(0,initial['p2']['hp']-hps[1]),
          'damage_taken_hp':max(0,initial['p1']['hp']-hps[0]),'elapsed_frame':trace['elapsed_frame'],
          'requested_action_counts':dict(Counter(str(t['action']) for t in trace['transitions']))}
    results={label:[] for label in adapters}
    for case in HOLDOUT_SUITE:
        for label,adapter in adapters.items():
            results[label].append({**case,'metrics':match(label,case,adapter)})
    labels=list(adapters)
    if len(labels)!=2:raise ValueError('exactly two candidates required')
    a,b=labels
    def aggregate(rows):
        return {'wins':sum(x['metrics']['winner']=='GARNET' for x in rows),
          'losses':sum(x['metrics']['winner'] not in ('GARNET','DRAW') for x in rows),
          'draws':sum(x['metrics']['winner']=='DRAW' for x in rows),
          'damage_dealt_hp':sum(x['metrics']['damage_dealt_hp'] for x in rows),
          'damage_taken_hp':sum(x['metrics']['damage_taken_hp'] for x in rows),
          'net_hp':sum(x['metrics']['damage_dealt_hp']-x['metrics']['damage_taken_hp'] for x in rows)}
    summary={'schema_version':1,'status':'PASS','kind':'independent-candidate-holdout-v1',
      'learning_performed':False,'policy_pixel_access':False,'readout_mode_p1':READOUT_MODE,
      'interpretation_boundary':'Independent no-learning engineering evaluation on seeds excluded from training, legacy replay, and candidate-selection validation. Six rounds are evidence, not proof of general strength.',
      'suite':HOLDOUT_SUITE,'candidates':identities,'results':results,'aggregate':{k:aggregate(v) for k,v in results.items()}}
    summary['delta_'+b+'_minus_'+a]={k:summary['aggregate'][b][k]-summary['aggregate'][a][k] for k in ('wins','losses','draws','damage_dealt_hp','damage_taken_hp','net_hp')}
    write(out/'independent-holdout.json',summary);print(json.dumps(summary,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
