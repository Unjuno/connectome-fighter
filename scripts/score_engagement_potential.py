#!/usr/bin/env python3
"""Offline-score a potential-based horizontal engagement shaping signal.

No action label is rewarded. The shaping potential is zero inside a candidate
contact band and decreases with horizontal separation outside that band. Only
potential differences are rewarded, so moving closer gives positive signal and
moving farther gives equal-magnitude negative signal.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def sign(x): return 1.0 if x>0 else -1.0 if x<0 else 0.0

def percentile(values,q):
    if not values:return 0.0
    x=sorted(float(v) for v in values); p=(len(x)-1)*q; lo=math.floor(p); hi=math.ceil(p)
    return x[lo] if lo==hi else x[lo]+(x[hi]-x[lo])*(p-lo)

def describe(values):
    v=[float(x) for x in values]; a=[abs(x) for x in v]; nz=[x for x in v if x!=0]
    return {'n':len(v),'nonzero':len(nz),'nonzero_rate':len(nz)/len(v) if v else 0.0,
            'positive':sum(x>0 for x in v),'negative':sum(x<0 for x in v),
            'mean':statistics.fmean(v) if v else 0.0,'mean_abs':statistics.fmean(a) if a else 0.0,
            'std':statistics.pstdev(v) if len(v)>1 else 0.0,'p95_abs':percentile(a,0.95),'max_abs':max(a,default=0.0)}

def distance(t):
    d=t.get('display') or {}; p1=d.get('p1') or {}; p2=d.get('p2') or {}
    x1=float(p1['x']); x2=float(p2['x'])
    if not (math.isfinite(x1) and math.isfinite(x2)): raise ValueError('non-finite x')
    return abs(x1-x2)

def hp(t,side):
    d=t.get('display') or {}; key='p1' if side==0 else 'p2'; return float((d.get(key) or {})['hp'])

def discover(root):
    runs=[]
    for p1 in root.rglob('p1.jsonl'):
        rd=p1.parent; p2=rd/'p2.jsonl'; st=rd/'status.json'
        if not p2.is_file() or not st.is_file(): continue
        status=json.loads(st.read_text());
        if status.get('canonical') is not True: continue
        a,b=read_jsonl(p1),read_jsonl(p2)
        if a and len(a)==len(b): runs.append((status,a,b))
    if not runs: raise SystemExit('no canonical runs')
    return runs

def phi(d,contact,stage_width):
    return -max(d-contact,0.0)/stage_width

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--stage-width',type=float,default=960.0); p.add_argument('--damage-unit-hp',type=float,default=10.0)
    args=p.parse_args();
    if args.stage_width<=0 or args.damage_unit_hp<=0: p.error('scales must be positive')
    runs=discover(args.root)
    records=[]; distance_changes=[]
    for status,p1rows,p2rows in runs:
        for side,rows in ((0,p1rows),(1,p2rows)):
            for rix,row in enumerate(rows,1):
                ts=row.get('transitions') or []
                terminal=row.get('remaining_hps') or [0,0]
                term=sign(float(terminal[side])-float(terminal[1-side]))
                for i,t in enumerate(ts):
                    d0=distance(t)
                    if i+1<len(ts):
                        d1=distance(ts[i+1])
                        next_self=hp(ts[i+1],side); next_opp=hp(ts[i+1],1-side)
                    else:
                        d1=d0
                        next_self=float(terminal[side]); next_opp=float(terminal[1-side])
                    self0=hp(t,side); opp0=hp(t,1-side)
                    damage=(max(0,opp0-next_opp)-max(0,self0-next_self))/args.damage_unit_hp
                    records.append({'key':(status['run_id'],rix,side+1),'decision':i,'last':i==len(ts)-1,
                                    'd0':d0,'d1':d1,'damage':damage,'terminal':term if i==len(ts)-1 else 0.0})
                    if i+1<len(ts): distance_changes.append(d1-d0)
    configs=[]
    for contact in (120.0,180.0,240.0):
      raw_shape=[phi(r['d1'],contact,args.stage_width)-phi(r['d0'],contact,args.stage_width) for r in records]
      for potential_weight in (0.05,0.1,0.25):
        rewards=[]; grouped=defaultdict(float)
        for r,shape in zip(records,raw_shape):
            reward=0.1*r['damage'] + potential_weight*shape + r['terminal']
            rewards.append(reward); grouped[r['key']]+=reward
        configs.append({'contact_band_px':contact,'potential_weight':potential_weight,'damage_weight_per_10hp':0.1,
                        'terminal_win_loss_bonus':1.0,'decision_reward':describe(rewards),'round_return':describe(list(grouped.values())),
                        'raw_potential_delta':describe(raw_shape)})
    result={'schema_version':1,'status':'PASS','learning_performed':False,
            'candidate':'R2c-horizontal-engagement-potential',
            'definition':'phi(d)=-max(d-contact_band,0)/stage_width; shaping=potential_weight*(phi(d_next)-phi(d_now)); plus 0.1 per 10HP damage differential and terminal +/-1.',
            'decision_windows_per_brain':len(records),'game_rounds':len({(r['key'][0],r['key'][1]) for r in records}),
            'horizontal_distance_change_px':describe(distance_changes),'configs':configs,
            'guardrails':{'no_specific_action_reward':True,'same_trajectories':True,'current_action_randomness_unchanged':True,
                          'uses_game_geometry':True,'non_zero_sum_shaping':True,'engineering_shaping_not_endogenous_fly_reward':True,
                          'policy_invariance_not_claimed_for_this_partially_observed_recurrent_controller':True}}
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
