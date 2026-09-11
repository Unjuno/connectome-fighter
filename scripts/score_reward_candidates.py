#!/usr/bin/env python3
"""Offline-score canonical FightingICE trajectories under candidate reward designs.

This script never updates neural state. It reconstructs HP changes between
logged decision windows and reports reward density/range for several candidate
families while keeping the exact same game trajectories.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

MAX_HP_DEFAULT = 400.0
DAMAGE_UNIT_HP_DEFAULT = 10.0


def read_jsonl(path: Path) -> list[dict]:
    rows=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip(): rows.append(json.loads(line))
    return rows


def finite(x: float) -> float:
    x=float(x)
    if not math.isfinite(x): raise ValueError(f'non-finite value: {x}')
    return x


def sign(x: float) -> float:
    return 1.0 if x>0 else -1.0 if x<0 else 0.0


def hp_pair_from_transition(t: dict, side: int) -> tuple[float,float]:
    display=t.get('display') or {}
    self_key='p1' if side==0 else 'p2'
    opp_key='p2' if side==0 else 'p1'
    self_hp=finite((display.get(self_key) or {}).get('hp'))
    opp_hp=finite((display.get(opp_key) or {}).get('hp'))
    return self_hp,opp_hp


def round_events(round_row: dict, side: int, max_hp: float) -> dict:
    transitions=round_row.get('transitions') or []
    if not transitions:
        raise ValueError('round has no transitions')
    terminal=round_row.get('remaining_hps')
    if not isinstance(terminal,list) or len(terminal)!=2:
        raise ValueError('round missing remaining_hps')
    final_self=finite(terminal[side]); final_opp=finite(terminal[1-side])
    if not (0<=final_self<=max_hp and 0<=final_opp<=max_hp):
        raise ValueError('terminal HP outside expected range')

    events=[]
    for i,t in enumerate(transitions):
        self_hp,opp_hp=hp_pair_from_transition(t,side)
        if i+1<len(transitions):
            next_self,next_opp=hp_pair_from_transition(transitions[i+1],side)
        else:
            next_self,next_opp=final_self,final_opp
        dealt=max(0.0,opp_hp-next_opp)
        taken=max(0.0,self_hp-next_self)
        # HP gains are not rewarded; log them explicitly as anomalies/regen.
        self_gain=max(0.0,next_self-self_hp)
        opp_gain=max(0.0,next_opp-opp_hp)
        events.append({
            'decision_index':i,
            'frame':int(t.get('frame',i)),
            'action':int(t.get('action',0)),
            'self_hp_before':self_hp,
            'opp_hp_before':opp_hp,
            'self_hp_after':next_self,
            'opp_hp_after':next_opp,
            'damage_dealt_hp':dealt,
            'damage_taken_hp':taken,
            'damage_delta_hp':dealt-taken,
            'self_hp_gain':self_gain,
            'opp_hp_gain':opp_gain,
        })
    margin=final_self-final_opp
    logged=finite(round_row.get('outcome_reward',sign(margin)))
    if logged!=sign(margin):
        raise ValueError(f'logged outcome_reward {logged} disagrees with HP margin {margin}')
    return {
        'events':events,
        'final_self_hp':final_self,
        'final_opp_hp':final_opp,
        'final_margin_hp':margin,
        'terminal_sign':sign(margin),
    }


def percentile(values: list[float], q: float) -> float:
    if not values: return 0.0
    x=sorted(values)
    if len(x)==1: return float(x[0])
    pos=(len(x)-1)*q
    lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi: return float(x[lo])
    return float(x[lo]+(x[hi]-x[lo])*(pos-lo))


def describe(values: list[float]) -> dict:
    vals=[float(v) for v in values]
    absvals=[abs(v) for v in vals]
    nz=[v for v in vals if v!=0.0]
    return {
        'n':len(vals),
        'nonzero':len(nz),
        'nonzero_rate':len(nz)/len(vals) if vals else 0.0,
        'positive':sum(v>0 for v in vals),
        'negative':sum(v<0 for v in vals),
        'mean':statistics.fmean(vals) if vals else 0.0,
        'mean_abs':statistics.fmean(absvals) if vals else 0.0,
        'std':statistics.pstdev(vals) if len(vals)>1 else 0.0,
        'p95_abs':percentile(absvals,0.95),
        'max_abs':max(absvals,default=0.0),
    }


def discover_runs(root: Path) -> list[dict]:
    runs=[]
    for p1 in sorted(root.rglob('p1.jsonl')):
        run_dir=p1.parent
        p2=run_dir/'p2.jsonl'; status_path=run_dir/'status.json'
        if not p2.is_file() or not status_path.is_file(): continue
        status=json.loads(status_path.read_text(encoding='utf-8'))
        if status.get('canonical') is not True: continue
        chars=status.get('characters') or []
        seeds=status.get('seeds') or []
        if len(chars)!=2 or len(seeds)!=2: continue
        a,b=read_jsonl(p1),read_jsonl(p2)
        if not a or len(a)!=len(b): continue
        runs.append({'run_dir':run_dir,'run_id':status.get('run_id',run_dir.name),'characters':chars,'seeds':seeds,'p1':a,'p2':b})
    if not runs: raise SystemExit('No canonical p1/p2 trajectory pairs found')
    return runs


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--out-json',type=Path,required=True)
    p.add_argument('--out-csv',type=Path,required=True)
    p.add_argument('--max-hp',type=float,default=MAX_HP_DEFAULT)
    p.add_argument('--damage-unit-hp',type=float,default=DAMAGE_UNIT_HP_DEFAULT)
    args=p.parse_args()
    if args.max_hp<=0 or args.damage_unit_hp<=0: p.error('HP scales must be positive')

    runs=discover_runs(args.root)
    event_rows=[]; round_rows=[]
    pair_keys=set(); action_counts=Counter()
    for run in runs:
        pair_keys.add(tuple(sorted((str(run['characters'][i]),int(run['seeds'][i])) for i in range(2))))
        for side in (0,1):
            character=str(run['characters'][side]); opponent=str(run['characters'][1-side])
            seed=int(run['seeds'][side]); opp_seed=int(run['seeds'][1-side])
            rows=run['p1'] if side==0 else run['p2']
            for rix,row in enumerate(rows, start=1):
                parsed=round_events(row,side,args.max_hp)
                margin=parsed['final_margin_hp']; terminal=parsed['terminal_sign']
                # R0: terminal sign only.
                # R1: terminal sign + normalized final HP margin, still terminal-only.
                r0_return=terminal
                r1_return=terminal + margin/args.max_hp
                # R2 component is reported without freezing one scale:
                # damage_component_units = (dealt-taken)/damage_unit_hp per window.
                damage_units=[e['damage_delta_hp']/args.damage_unit_hp for e in parsed['events']]
                round_rows.append({
                    'run_id':run['run_id'],'round':rix,'side':side+1,'character':character,'opponent':opponent,
                    'seed':seed,'opponent_seed':opp_seed,'decisions':len(parsed['events']),
                    'final_self_hp':parsed['final_self_hp'],'final_opp_hp':parsed['final_opp_hp'],
                    'final_margin_hp':margin,'terminal_sign':terminal,
                    'r0_return':r0_return,'r1_return':r1_return,
                    'damage_event_windows':sum(x!=0 for x in damage_units),
                    'damage_component_sum_units':sum(damage_units),
                    'damage_dealt_hp':sum(e['damage_dealt_hp'] for e in parsed['events']),
                    'damage_taken_hp':sum(e['damage_taken_hp'] for e in parsed['events']),
                })
                for e,du in zip(parsed['events'],damage_units):
                    action_counts[e['action']]+=1
                    event_rows.append({
                        'run_id':run['run_id'],'round':rix,'side':side+1,'character':character,'opponent':opponent,
                        'seed':seed,'opponent_seed':opp_seed,**e,
                        'r0_local':0.0,
                        'r1_local':0.0,
                        'r2_damage_component_units':du,
                        'terminal_sign_if_last':terminal if e['decision_index']==len(parsed['events'])-1 else 0.0,
                    })

    # Each game is represented from both players. Decision-window density is side-specific,
    # which is appropriate for a per-brain reward signal. Round-level game counts divide by two.
    terminal_signs=[r['terminal_sign'] for r in round_rows]
    margins=[r['final_margin_hp'] for r in round_rows]
    damage_units=[e['r2_damage_component_units'] for e in event_rows]
    terminal_events=[e['terminal_sign_if_last'] for e in event_rows]

    r0_sequence=[e['terminal_sign_if_last'] for e in event_rows]
    # R1 remains terminal-only; put the margin term on the final decision.
    round_by_key={(r['run_id'],r['round'],r['side']):r for r in round_rows}
    r1_sequence=[]
    for e in event_rows:
        r=round_by_key[(e['run_id'],e['round'],e['side'])]
        if e['decision_index']==r['decisions']-1: r1_sequence.append(r['r1_return'])
        else: r1_sequence.append(0.0)

    scale_grid=[]
    for damage_weight in (0.05,0.1,0.25,0.5,1.0):
        for terminal_bonus in (0.25,0.5,1.0):
            seq=[damage_weight*d + terminal_bonus*t for d,t in zip(damage_units,terminal_events)]
            returns=[]
            grouped=defaultdict(float)
            for e,reward in zip(event_rows,seq): grouped[(e['run_id'],e['round'],e['side'])]+=reward
            returns=list(grouped.values())
            scale_grid.append({
                'damage_weight_per_damage_unit':damage_weight,
                'damage_unit_hp':args.damage_unit_hp,
                'terminal_bonus':terminal_bonus,
                'decision_reward':describe(seq),
                'round_return':describe(returns),
            })

    summary={
        'schema_version':1,
        'status':'PASS',
        'learning_performed':False,
        'interpretation':'Offline rescoring only; no action, LIF, synapse, checkpoint, or RNG state was changed.',
        'input':{
            'canonical_runs':len(runs),
            'unique_character_seed_pairings':len(pair_keys),
            'side_rounds':len(round_rows),
            'game_rounds':len(round_rows)//2,
            'decision_windows_per_brain':len(event_rows),
            'max_hp':args.max_hp,
            'damage_unit_hp':args.damage_unit_hp,
        },
        'observed':{
            'terminal_outcomes':describe(terminal_signs),
            'final_hp_margin':describe(margins),
            'damage_component_units':describe(damage_units),
            'damage_windows_per_brain':sum(d!=0 for d in damage_units),
            'damage_window_rate':sum(d!=0 for d in damage_units)/len(damage_units) if damage_units else 0.0,
            'rounds_with_any_damage_signal_per_brain':sum(r['damage_event_windows']>0 for r in round_rows),
            'action_counts_by_id':{str(k):int(v) for k,v in sorted(action_counts.items())},
        },
        'candidate_families':{
            'R0_terminal_sign':{
                'definition':'all decision rewards 0 except final decision = sign(final_self_hp-final_opp_hp)',
                'decision_reward':describe(r0_sequence),
                'round_return':describe([r['r0_return'] for r in round_rows]),
            },
            'R1_terminal_sign_plus_margin':{
                'definition':'all decision rewards 0 except final = sign(margin)+margin/max_hp',
                'decision_reward':describe(r1_sequence),
                'round_return':describe([r['r1_return'] for r in round_rows]),
            },
            'R2_damage_local_plus_terminal_grid':{
                'component_definition':'per decision damage_component=(damage_dealt_hp-damage_taken_hp)/damage_unit_hp; candidate reward = damage_weight*damage_component + terminal_bonus*terminal_sign_on_final_decision',
                'scale_grid':scale_grid,
            },
        },
        'guardrails':{
            'no_action_shaping':True,
            'no_reward_for_forward_or_attack_button':True,
            'same_logged_trajectories_for_all_candidates':True,
            'current_action_randomness_unchanged':True,
        },
    }

    args.out_json.parent.mkdir(parents=True,exist_ok=True)
    args.out_json.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    args.out_csv.parent.mkdir(parents=True,exist_ok=True)
    fields=list(event_rows[0].keys())
    with args.out_csv.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(event_rows)
    print(json.dumps(summary,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
