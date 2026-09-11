#!/usr/bin/env python3
"""Offline-score R2d: engagement potential + no-damage stalemate penalty.

This is an engineering curriculum candidate. It rewards no action label. Local
potential differences provide a small positive/negative engagement signal,
damage differential remains outcome-based, and no-damage draws receive one
small terminal penalty.
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

def sign(x): return 1.0 if x > 0 else -1.0 if x < 0 else 0.0

def percentile(values, q):
    if not values: return 0.0
    x=sorted(float(v) for v in values); p=(len(x)-1)*q; lo=math.floor(p); hi=math.ceil(p)
    return x[lo] if lo==hi else x[lo]+(x[hi]-x[lo])*(p-lo)

def describe(values):
    v=[float(x) for x in values]; a=[abs(x) for x in v]; nz=[x for x in v if x != 0]
    return {
        'n':len(v),'nonzero':len(nz),'nonzero_rate':len(nz)/len(v) if v else 0.0,
        'positive':sum(x>0 for x in v),'negative':sum(x<0 for x in v),
        'mean':statistics.fmean(v) if v else 0.0,
        'mean_abs':statistics.fmean(a) if a else 0.0,
        'std':statistics.pstdev(v) if len(v)>1 else 0.0,
        'p95_abs':percentile(a,0.95),'max_abs':max(a,default=0.0),
    }

def distance(t):
    d=t.get('display') or {}; p1=d.get('p1') or {}; p2=d.get('p2') or {}
    return abs(float(p1['x'])-float(p2['x']))

def hp(t, side):
    d=t.get('display') or {}; key='p1' if side==0 else 'p2'; return float((d.get(key) or {})['hp'])

def phi(d, contact_band, stage_width):
    return -max(d-contact_band, 0.0)/stage_width

def discover(root):
    out=[]
    for p1 in root.rglob('p1.jsonl'):
        rd=p1.parent; p2=rd/'p2.jsonl'; st=rd/'status.json'
        if not p2.is_file() or not st.is_file(): continue
        status=json.loads(st.read_text(encoding='utf-8'))
        if status.get('canonical') is not True: continue
        a,b=read_jsonl(p1),read_jsonl(p2)
        if a and len(a)==len(b): out.append((status,a,b))
    if not out: raise SystemExit('no canonical runs')
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--stage-width',type=float,default=960.0)
    p.add_argument('--damage-unit-hp',type=float,default=10.0)
    args=p.parse_args()
    runs=discover(args.root)
    episodes=[]
    for status,p1rows,p2rows in runs:
        for side,rows in ((0,p1rows),(1,p2rows)):
            for rix,row in enumerate(rows,1):
                ts=row.get('transitions') or []
                if not ts: raise ValueError('empty round')
                terminal=row.get('remaining_hps') or [0,0]
                terminal_sign=sign(float(terminal[side])-float(terminal[1-side]))
                events=[]; total_damage=0.0
                for i,t in enumerate(ts):
                    d0=distance(t)
                    if i+1 < len(ts):
                        d1=distance(ts[i+1]); next_self=hp(ts[i+1],side); next_opp=hp(ts[i+1],1-side)
                    else:
                        d1=d0; next_self=float(terminal[side]); next_opp=float(terminal[1-side])
                    self0=hp(t,side); opp0=hp(t,1-side)
                    dealt=max(0.0,opp0-next_opp); taken=max(0.0,self0-next_self)
                    total_damage += dealt+taken
                    events.append({'d0':d0,'d1':d1,'damage_units':(dealt-taken)/args.damage_unit_hp,'last':i==len(ts)-1})
                episodes.append({'key':(status['run_id'],rix,side+1),'events':events,'terminal_sign':terminal_sign,'no_damage':total_damage==0.0})

    configs=[]
    for contact in (120.0,180.0,240.0):
      for potential_weight in (0.05,0.10):
       for stalemate_penalty in (0.01,0.02,0.05):
        decision_rewards=[]; round_returns=[]
        positive_potential=negative_potential=0
        for ep in episodes:
            ret=0.0
            for e in ep['events']:
                delta=phi(e['d1'],contact,args.stage_width)-phi(e['d0'],contact,args.stage_width)
                if delta>0: positive_potential+=1
                elif delta<0: negative_potential+=1
                r=potential_weight*delta + 0.1*e['damage_units']
                if e['last']:
                    if ep['terminal_sign'] != 0:
                        r += ep['terminal_sign']
                    elif ep['no_damage']:
                        r -= stalemate_penalty
                decision_rewards.append(r); ret += r
            round_returns.append(ret)
        configs.append({
            'contact_band_px':contact,
            'potential_weight':potential_weight,
            'damage_weight_per_10hp':0.10,
            'terminal_win_loss_bonus':1.0,
            'no_damage_draw_penalty':stalemate_penalty,
            'potential_events':{'positive':positive_potential,'negative':negative_potential},
            'decision_reward':describe(decision_rewards),
            'round_return':describe(round_returns),
        })
    result={
        'schema_version':1,'status':'PASS','learning_performed':False,
        'candidate':'R2d-engagement-potential-plus-stalemate',
        'definition':'0.1*((damage_dealt-damage_taken)/10HP) + w_phi*(phi(d_next)-phi(d_now)); terminal +/-1 for win/loss; otherwise -delta only for zero-damage draw.',
        'phi':'-max(horizontal_distance-contact_band,0)/960',
        'brain_rounds':len(episodes),'game_rounds':len(episodes)//2,
        'no_damage_brain_rounds':sum(ep['no_damage'] and ep['terminal_sign']==0 for ep in episodes),
        'configs':configs,
        'guardrails':{
            'no_specific_action_reward':True,
            'no_attack_button_reward':True,
            'same_trajectories':True,
            'current_action_randomness_unchanged':True,
            'uses_game_geometry':True,
            'engineering_curriculum_not_endogenous_fly_reward':True,
        },
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
