#!/usr/bin/env python3
"""Apply one audited game match to one character's MaleCNS KC->MBON state.

This post-match updater consumes already logged game telemetry and body-ID spike
events. It never changes topology or transmitter sign. Positive game signal
only depresses eligible KC inputs to avoidance-associated MBONs; negative signal
only depresses eligible KC inputs to approach-associated MBONs.

The reward JSON and plasticity JSON must explicitly reference the same reward ID.
This allows paired reward experiments (for example R2c-v0 vs R2d-v0) without
silently changing the neural plasticity rule.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from connectome_fighter.valence_plasticity import (
    ValencePlasticityConfig,
    apply_modulatory_signal,
    finish_match,
    initialize_state,
    load_state,
    save_state,
    sha256_file,
    update_eligibility,
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def sgn(x: float) -> float:
    return 1.0 if x>0 else -1.0 if x<0 else 0.0


def hp(t:dict,side:int)->float:
    d=t.get('display') or {}; return float((d.get('p1' if side==0 else 'p2') or {})['hp'])


def distance(t:dict)->float:
    d=t.get('display') or {}; return abs(float((d.get('p1') or {})['x'])-float((d.get('p2') or {})['x']))


def phi(distance_px:float,reward_cfg:dict)->float:
    c=reward_cfg['engagement_potential']; return -max(distance_px-float(c['contact_band_px']),0.0)/float(c['stage_width_px'])


def plasticity_config(raw:dict,reward_id:str)->ValencePlasticityConfig:
    return ValencePlasticityConfig(
        learning_rate=float(raw['learning_rate_per_unit_modulatory_signal']),
        eligibility_decay=float(raw['eligibility_decay_per_decision']),
        pair_count_cap=float(raw['pair_count_cap']),
        normalization_percentile=float(raw['normalization_percentile']),
        multiplier_min=float(raw['multiplier_min']),
        multiplier_max=float(raw['multiplier_max']),
        positive_target=str(raw['positive_signal_target']),
        negative_target=str(raw['negative_signal_target']),
        reward_id=reward_id,
    )


def reward_sequence(round_row:dict,side:int,reward_cfg:dict)->list[dict]:
    ts=round_row.get('transitions') or []
    terminal=round_row.get('remaining_hps')
    if not ts or not isinstance(terminal,list) or len(terminal)!=2: raise ValueError('invalid round trace')
    events=[]; total_damage=0.0
    for i,t in enumerate(ts):
        self0=hp(t,side); opp0=hp(t,1-side); d0=distance(t)
        if i+1<len(ts):
            nxt=ts[i+1]; self1=hp(nxt,side); opp1=hp(nxt,1-side); d1=distance(nxt)
        else:
            self1=float(terminal[side]); opp1=float(terminal[1-side]); d1=d0
        dealt=max(0.0,opp0-opp1); taken=max(0.0,self0-self1); total_damage+=dealt+taken
        damage_cfg=reward_cfg['damage']; pot=reward_cfg['engagement_potential']
        damage_reward=float(damage_cfg['weight_per_unit'])*((dealt-taken)/float(damage_cfg['unit_hp']))
        potential_reward=float(pot['weight'])*(phi(d1,reward_cfg)-phi(d0,reward_cfg)) if bool(pot.get('enabled',True)) else 0.0
        trace_decision=int(((t.get('brain') or {}).get('trace_decision_index',i)))
        events.append({'decision_index':trace_decision,'frame':int(t.get('frame',i)),'damage_reward':damage_reward,'potential_reward':potential_reward,'signal':damage_reward+potential_reward,'last':i==len(ts)-1})
    margin=float(terminal[side])-float(terminal[1-side]); terminal_sign=sgn(margin)
    if terminal_sign>0: final_extra=float(reward_cfg['terminal']['win'])
    elif terminal_sign<0: final_extra=float(reward_cfg['terminal']['loss'])
    elif total_damage==0.0: final_extra=float(reward_cfg['terminal'].get('no_damage_draw_penalty',0.0))
    else: final_extra=float(reward_cfg['terminal'].get('ordinary_draw',0.0))
    events[-1]['terminal_reward']=final_extra; events[-1]['signal']+=final_extra
    for e in events[:-1]: e['terminal_reward']=0.0
    return events


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--character',required=True)
    p.add_argument('--side',type=int,choices=[1,2],required=True)
    p.add_argument('--round-trace',type=Path,required=True)
    p.add_argument('--spikes',type=Path,required=True)
    p.add_argument('--candidates',type=Path,required=True)
    p.add_argument('--reward-config',type=Path,required=True)
    p.add_argument('--plasticity-config',type=Path,required=True)
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--round-index',type=int,default=0)
    p.add_argument('--out-summary',type=Path,required=True)
    args=p.parse_args()

    reward_cfg=json.loads(args.reward_config.read_text(encoding='utf-8'))
    reward_id=str(reward_cfg.get('id') or '').strip()
    if not reward_id: raise ValueError('reward config id missing')
    raw_plastic=json.loads(args.plasticity_config.read_text(encoding='utf-8'))
    if str(raw_plastic.get('reward_config') or '')!=reward_id: raise ValueError('plasticity/reward config mismatch')
    cfg=plasticity_config(raw_plastic,reward_id); cfg.validate()

    candidates=pd.read_parquet(args.candidates).sort_values('synapse_index').reset_index(drop=True)
    required={'body_pre','body_post','mbon_valence_channel','sign','synapse_index'}
    if not required.issubset(candidates.columns) or candidates.empty: raise ValueError('invalid valence candidate table')
    if not (candidates['sign']==1).all(): raise ValueError('candidate sign invariant failed')
    channels=candidates['mbon_valence_channel'].astype(str).to_numpy()
    if set(channels)-{'approach_associated','avoidance_associated'}: raise ValueError('unresolved candidate channels')
    candidate_sha=sha256_file(args.candidates)

    rounds=read_jsonl(args.round_trace)
    if args.round_index<0 or args.round_index>=len(rounds): raise IndexError('round-index outside trace')
    events=reward_sequence(rounds[args.round_index],args.side-1,reward_cfg)

    spikes=pd.read_parquet(args.spikes)
    if not {'decision_index','body_id'}.issubset(spikes.columns): raise ValueError('spike log missing columns')
    counts=spikes.groupby(['decision_index','body_id']).size() if not spikes.empty else pd.Series(dtype=np.int64)
    pre=candidates['body_pre'].to_numpy(dtype=np.int64); post=candidates['body_post'].to_numpy(dtype=np.int64)

    if args.state.is_file():
        state=load_state(args.state,expected_character=args.character,n_candidates=len(candidates),expected_candidate_sha256=candidate_sha,config=cfg)
        source='checkpoint'
    else:
        state=initialize_state(character=args.character,n_candidates=len(candidates),candidate_sha256=candidate_sha,config=cfg)
        source='unity-initial-state'
    before=state.multipliers.copy(); eligibility=np.zeros(len(candidates),dtype=np.float64); event_metrics=[]
    for event in events:
        decision=int(event['decision_index'])
        if not spikes.empty and decision in counts.index.get_level_values(0): series=counts.loc[decision]
        else: series=pd.Series(dtype=np.int64)
        pre_counts=series.reindex(pre,fill_value=0).to_numpy(dtype=np.float64)
        post_counts=series.reindex(post,fill_value=0).to_numpy(dtype=np.float64)
        eligibility=update_eligibility(eligibility,pre_counts,post_counts,cfg)
        metrics=apply_modulatory_signal(state,eligibility,float(event['signal']),channels,cfg)
        event_metrics.append({**event,**metrics})
    finish_match(state)
    state_meta=save_state(args.state,state,cfg)
    after=state.multipliers.astype(np.float64); before64=before.astype(np.float64)
    changed=np.flatnonzero(np.abs(after-before64)>1e-12)
    approach=(channels=='approach_associated'); avoidance=(channels=='avoidance_associated')
    summary={
        'status':'PASS','model':'KC-MBON-valence-depression-v0','reward_id':reward_id,'character':args.character,'side':args.side,
        'round_index':args.round_index,'state_source':source,'candidate_edges':int(len(candidates)),
        'channels':{'approach_edges':int(approach.sum()),'avoidance_edges':int(avoidance.sum())},
        'signals':{
            'decision_windows':len(events),'nonzero':sum(float(e['signal'])!=0.0 for e in events),
            'positive':sum(float(e['signal'])>0 for e in events),'negative':sum(float(e['signal'])<0 for e in events),
            'sum':float(sum(float(e['signal']) for e in events)),
        },
        'updates':{
            'changed_edges':int(len(changed)),
            'changed_approach_edges':int(np.count_nonzero(approach[changed])) if len(changed) else 0,
            'changed_avoidance_edges':int(np.count_nonzero(avoidance[changed])) if len(changed) else 0,
            'potentiated_edges':int(np.count_nonzero(after>before64+1e-12)),
            'depressed_edges':int(np.count_nonzero(after<before64-1e-12)),
            'min_multiplier':float(after.min()),'mean_multiplier':float(after.mean()),'max_multiplier':float(after.max()),
        },
        'state':state_meta,
        'event_metrics':event_metrics,
        'invariants':{'topology_changed':False,'sign_changed':False,'potentiation_allowed':False,'only_existing_KC_MBON_edges':True},
        'interpretation_boundary':f'{reward_id} and its mapping to MBON valence channels are project-defined game-learning interfaces, not identified endogenous FightingICE reinforcement pathways in Drosophila.',
    }
    if summary['updates']['potentiated_edges']!=0 or summary['updates']['max_multiplier']>1.0000001: raise RuntimeError('depression-only invariant violated')
    args.out_summary.parent.mkdir(parents=True,exist_ok=True)
    args.out_summary.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['status','reward_id','character','signals','updates','state']},indent=2,sort_keys=True))
    return 0

if __name__=='__main__': raise SystemExit(main())
