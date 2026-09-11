#!/usr/bin/env python3
"""Summarize one fighter side from audited FightingICE round JSONL."""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
from pathlib import Path

ACTION_NAMES={0:'NEUTRAL',1:'FORWARD',2:'BACKWARD',3:'UP',4:'DOWN',5:'A',6:'B',7:'C'}

def read_jsonl(path:Path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace',type=Path,required=True)
    p.add_argument('--side',type=int,choices=[1,2],default=1)
    p.add_argument('--condition',required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); side=args.side-1
    rows=read_jsonl(args.trace)
    if not rows: raise SystemExit('empty trace')
    action_counts=collections.Counter(); round_stats=[]
    for ridx,row in enumerate(rows,1):
        ts=row.get('transitions') or []
        if not ts: raise ValueError('round without transitions')
        initial_distance=None; min_distance=math.inf; max_distance=0.0; moved_windows=0
        prev_distance=None; dealt=taken=0.0
        for i,t in enumerate(ts):
            d=t.get('display') or {}; pself=d.get('p1' if side==0 else 'p2') or {}; popp=d.get('p2' if side==0 else 'p1') or {}
            dist=abs(float(pself['x'])-float(popp['x']))
            if initial_distance is None: initial_distance=dist
            min_distance=min(min_distance,dist); max_distance=max(max_distance,dist)
            if prev_distance is not None and abs(dist-prev_distance)>1e-9: moved_windows+=1
            prev_distance=dist
            action_counts[int(t['action'])]+=1
            self0=float(pself['hp']); opp0=float(popp['hp'])
            if i+1<len(ts):
                nd=ts[i+1].get('display') or {}; nself=nd.get('p1' if side==0 else 'p2') or {}; nopp=nd.get('p2' if side==0 else 'p1') or {}
                self1=float(nself['hp']); opp1=float(nopp['hp'])
            else:
                terminal=row.get('remaining_hps') or [0,0]; self1=float(terminal[side]); opp1=float(terminal[1-side])
            dealt += max(0.0,opp0-opp1); taken += max(0.0,self0-self1)
        final=row.get('remaining_hps') or [0,0]; margin=float(final[side])-float(final[1-side]); reward=float(row.get('outcome_reward',0.0))
        round_stats.append({
            'round':ridx,'reward':reward,'final_margin_hp':margin,'damage_dealt_hp':dealt,'damage_taken_hp':taken,
            'initial_distance_px':initial_distance,'min_distance_px':min_distance,'max_distance_px':max_distance,
            'distance_reduction_px':float(initial_distance-min_distance),'moved_decision_windows':moved_windows,
        })
    def mean(key): return statistics.fmean(float(r[key]) for r in round_stats)
    total_actions=sum(action_counts.values())
    summary={
        'schema_version':1,'condition':args.condition,'side':args.side,'rounds':len(rows),
        'wins':sum(r['reward']>0 for r in round_stats),'losses':sum(r['reward']<0 for r in round_stats),'draws':sum(r['reward']==0 for r in round_stats),
        'damage_rounds':sum((r['damage_dealt_hp']+r['damage_taken_hp'])>0 for r in round_stats),
        'total_damage_dealt_hp':sum(r['damage_dealt_hp'] for r in round_stats),'total_damage_taken_hp':sum(r['damage_taken_hp'] for r in round_stats),
        'mean_final_margin_hp':mean('final_margin_hp'),'mean_min_distance_px':mean('min_distance_px'),'mean_distance_reduction_px':mean('distance_reduction_px'),
        'rounds_with_distance_reduction':sum(r['distance_reduction_px']>0 for r in round_stats),
        'moved_decision_windows':sum(r['moved_decision_windows'] for r in round_stats),
        'action_counts':{ACTION_NAMES.get(k,str(k)):int(v) for k,v in sorted(action_counts.items())},
        'action_rates':{ACTION_NAMES.get(k,str(k)):float(v/total_actions) for k,v in sorted(action_counts.items())},
        'round_detail':round_stats,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['condition','rounds','wins','losses','draws','damage_rounds','total_damage_dealt_hp','mean_min_distance_px','mean_distance_reduction_px','rounds_with_distance_reduction','action_rates']},indent=2,sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
