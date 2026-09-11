#!/usr/bin/env python3
"""Compare damage-local rewards with a small no-damage-draw penalty offline."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def percentile(values,q):
    if not values:return 0.0
    x=sorted(float(v) for v in values); pos=(len(x)-1)*q
    lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi:return x[lo]
    return x[lo]+(x[hi]-x[lo])*(pos-lo)


def describe(values):
    v=[float(x) for x in values]; a=[abs(x) for x in v]; nz=[x for x in v if x!=0]
    return {'n':len(v),'nonzero':len(nz),'nonzero_rate':len(nz)/len(v) if v else 0.0,
            'positive':sum(x>0 for x in v),'negative':sum(x<0 for x in v),
            'mean':statistics.fmean(v) if v else 0.0,'mean_abs':statistics.fmean(a) if a else 0.0,
            'std':statistics.pstdev(v) if len(v)>1 else 0.0,'p95_abs':percentile(a,0.95),'max_abs':max(a,default=0.0)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    rows=[]
    with args.events.open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            r['round']=int(r['round']); r['side']=int(r['side']); r['decision_index']=int(r['decision_index'])
            for k in ['r2_damage_component_units','terminal_sign_if_last','damage_dealt_hp','damage_taken_hp']:
                r[k]=float(r[k])
            rows.append(r)
    if not rows: raise SystemExit('empty reward event table')
    groups=defaultdict(list)
    for r in rows: groups[(r['run_id'],r['round'],r['side'])].append(r)
    no_damage={k:(sum(x['damage_dealt_hp']+x['damage_taken_hp'] for x in v)==0.0) for k,v in groups.items()}
    configs=[]
    for damage_weight in (0.05,0.1,0.25):
        for stalemate_penalty in (0.01,0.02,0.05,0.1,0.25):
            decision_rewards=[]; returns=[]
            for key,events in groups.items():
                total=0.0
                last=max(x['decision_index'] for x in events)
                for e in sorted(events,key=lambda x:x['decision_index']):
                    reward=damage_weight*e['r2_damage_component_units']
                    if e['decision_index']==last:
                        terminal=e['terminal_sign_if_last']
                        if terminal!=0:
                            reward += terminal
                        elif no_damage[key]:
                            reward -= stalemate_penalty
                    decision_rewards.append(reward); total+=reward
                returns.append(total)
            configs.append({
                'damage_weight_per_10hp':damage_weight,
                'terminal_win_loss_bonus':1.0,
                'no_damage_draw_penalty':stalemate_penalty,
                'decision_reward':describe(decision_rewards),
                'round_return':describe(returns),
            })
    result={
        'schema_version':1,'status':'PASS','learning_performed':False,
        'candidate':'R2b-damage-local-plus-terminal-plus-no-damage-draw-penalty',
        'definition':(
            'damage_weight*((damage_dealt-damage_taken)/10HP) per decision; '
            '+1/-1 on terminal win/loss; on an equal-HP round with zero damage exchanged, '
            'apply only a small negative reward on the final decision.'
        ),
        'rounds_per_brain':len(groups),
        'game_rounds':len(groups)//2,
        'no_damage_draw_rounds_per_brain':sum(no_damage.values()),
        'no_damage_draw_rate':sum(no_damage.values())/len(groups),
        'configs':configs,
        'guardrails':{
            'no_specific_action_reward':True,
            'no_distance_or_forward_shaping':True,
            'same_trajectories':True,
            'current_action_randomness_unchanged':True,
            'non_zero_sum_on_stalemate':True,
            'engineering_shaping_not_endogenous_fly_reward':True,
        },
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
