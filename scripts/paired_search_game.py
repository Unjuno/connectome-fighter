#!/usr/bin/env python3
"""One real FightingICE round for isolated neural-search/cadence experiments.

P1 is always the real MaleCNS/Shiu controller. P2 is explicitly either a neutral
training dummy or the canonical baseline. No weights change within a round.
Per-frame samples are delayed FrameData, observational only.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--adapter',type=Path,required=True)
    p.add_argument('--reference-python',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--opponent',choices=['neutral','canonical'],required=True)
    p.add_argument('--decision-interval',type=int,choices=[15,30,60],default=60)
    p.add_argument('--timeout',type=int,default=300)
    p.add_argument('--video',action='store_true')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    from pyftg.socket.aio.gateway import Gateway
    from connectome_fighter.contracts import Decision
    from connectome_fighter.malecns_worker_policy import MaleCNSWorkerPolicy
    from connectome_fighter.pyftg_bridge import FighterAI, _display_frame
    from connectome_fighter.trajectory import JsonlSink
    from connectome_fighter.match_audit import audit_pair
    from connectome_fighter.paired_search import score_round
    from connectome_fighter.fightingice_spectator import FightingICEScreenRecorder

    class Neutral:
        version='explicit-neutral-training-dummy-v1'
        def reset(self):pass
        def act(self, observation):return Decision(0,0.,0.,self.version)
        def close(self):pass

    class RecordedAI(FighterAI):
        def get_information(self,frame_data,is_control):
            super().get_information(frame_data,is_control)
            data=_display_frame(frame_data)
            if data and data['frame']>0:
                # A frame can be sent more than once; never inflate progress.
                if not samples or data['frame']>samples[-1]['frame']:
                    data['p1']['engine_action']=str(getattr(frame_data.character_data[0],'action','unavailable'))
                    data['p2']['engine_action']=str(getattr(frame_data.character_data[1],'action','unavailable'))
                    samples.append(data)
                    sample_handle.write(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n')
                elif data['frame']<samples[-1]['frame']:
                    raise RuntimeError('sample frame regressed')

    policies=[];agents=[];recorder=None;samples=[]
    sample_handle=(args.out/'observed-frames.jsonl').open('w')
    status={'status':'FAILED','opponent_mode':args.opponent,'p1_controller':'MaleCNS/Shiu LIF',
            'seed_p1':args.seed,'seed_p2':20202,'decision_interval_frames':args.decision_interval,
            'learning_performed':False,'policy_pixel_access':False,'synthetic_neural_fixture':False,
            'strength_claim':False}
    try:
        def brain(character,seed,adapter,side):
            manifest=json.loads((adapter/'manifest.json').read_text())
            version='paired-'+character+'-'+manifest['output_hashes']['connectivity_sha256'][:16]
            return MaleCNSWorkerPolicy(character=character,seed=seed,version=version,
                python_executable=args.reference_python,
                worker_script=args.runtime_root/'repo/scripts/malecns_lif_worker.py',
                reference_model=args.runtime_root/'shiu/model.py',adapter_dir=adapter,
                interface_path=args.runtime_root/'data/interface.json',
                trace_root=args.out/f'p{side}-brain',run_id=args.out.name+f'-p{side}')
        policies.append(brain('GARNET',args.seed,args.adapter,1))
        policies.append(Neutral() if args.opponent=='neutral' else brain('ZEN',20202,args.runtime_root/'data/malecns-shiu-strict-v1',2))
        status['workers']=[p.worker_ready for p in policies if hasattr(p,'worker_ready')]
        expected=1 if args.opponent=='neutral' else 2
        if len(status['workers'])!=expected or not all(w['neurons']==156675 and w['synapses']==6025920 for w in status['workers']):
            raise RuntimeError('canonical worker identity mismatch')
        for i,policy in enumerate(policies):
            cls=RecordedAI if i==0 else FighterAI
            agents.append(cls('paired-search-p'+str(i+1),policy,JsonlSink(args.out/f'p{i+1}.jsonl'),
                              args.out.name,policies[1-i].version,decision_interval=args.decision_interval,trainable=False))
        if args.video:
            recorder=FightingICEScreenRecorder(args.out/'screen.mp4',fps=10,ffmpeg='ffmpeg')
        async def play():
            gateway=Gateway(host='127.0.0.1',port=31415)
            task=None
            try:
                for ai in agents:gateway.register_ai(ai.name(),ai)
                if recorder:
                    gateway.register_stream(recorder)
                    task=asyncio.create_task(gateway.start_stream(keep_alive=False))
                    await asyncio.sleep(.25)
                await asyncio.wait_for(gateway.run_game(['GARNET','ZEN'],[a.name() for a in agents],1),args.timeout)
                if task:
                    try:await asyncio.wait_for(task,timeout=15)
                    except asyncio.TimeoutError:task.cancel();await asyncio.gather(task,return_exceptions=True)
            finally:
                if task and not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)
                for ai in agents:ai.close()
                if recorder:recorder.close()
                await asyncio.wait_for(gateway.close(),timeout=5)
        asyncio.run(play())
        sample_handle.flush()
        status['audit']=audit_pair(args.out/'p1.jsonl',args.out/'p2.jsonl',1,expected_trainable=False)
        rows=[json.loads(line) for line in (args.out/'p1.jsonl').read_text().splitlines() if line.strip()]
        if len(rows)!=1:raise RuntimeError('one complete round required')
        status['metrics']=score_round(rows[0],samples)
        if args.opponent=='neutral':
            p2=json.loads((args.out/'p2.jsonl').read_text().strip())
            if any(t['action']!=0 for t in p2['transitions']):raise RuntimeError('training dummy was not neutral')
        status['completed_rounds']=[a.ledger.completed for a in agents]
        if status['completed_rounds']!=[1,1]:raise RuntimeError('incomplete rounds')
        if recorder:
            status['spectator']=recorder.summary()
            if recorder.frames<=0 or (args.out/'screen.mp4').stat().st_size<10000:raise RuntimeError('unusable official video')
        status['status']='PASS'
        return 0
    except Exception:
        status['error']=traceback.format_exc();raise
    finally:
        for policy in policies:
            try:policy.close()
            except Exception:pass
        if recorder:
            try:recorder.close()
            except Exception:pass
        sample_handle.close()
        (args.out/'result.json').write_text(json.dumps(status,indent=2,sort_keys=True,allow_nan=False)+'\n')

if __name__=='__main__':raise SystemExit(main())
