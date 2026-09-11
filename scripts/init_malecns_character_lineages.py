#!/usr/bin/env python3
"""Initialize separate canonical MaleCNS plasticity states for FightingICE characters.

This creates four independent state files. It does not run a game and does not
apply learning. The files are intended to become the durable lineage bundle
once a reward/plasticity configuration has passed the selection gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from connectome_fighter.characters import CHARACTERS
from connectome_fighter.valence_plasticity import ValencePlasticityConfig, initialize_state, save_state, sha256_file


def config_from_json(path:Path)->tuple[ValencePlasticityConfig,dict]:
    raw=json.loads(path.read_text(encoding='utf-8'))
    cfg=ValencePlasticityConfig(
        learning_rate=float(raw['learning_rate_per_unit_modulatory_signal']),
        eligibility_decay=float(raw['eligibility_decay_per_decision']),
        pair_count_cap=float(raw['pair_count_cap']),
        normalization_percentile=float(raw['normalization_percentile']),
        multiplier_min=float(raw['multiplier_min']),multiplier_max=float(raw['multiplier_max']),
        positive_target=str(raw['positive_signal_target']),negative_target=str(raw['negative_signal_target']),
        reward_id=str(raw['reward_config']),
    )
    cfg.validate(); return cfg,raw


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidates',type=Path,required=True)
    p.add_argument('--plasticity-config',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    p.add_argument('--lineage-id',required=True)
    args=p.parse_args()
    candidates=pd.read_parquet(args.candidates,columns=['synapse_index','mbon_valence_channel','sign'])
    if candidates.empty or candidates['synapse_index'].duplicated().any(): raise ValueError('invalid candidate table')
    if not (candidates['sign']==1).all(): raise ValueError('candidate sign invariant failed')
    if set(candidates['mbon_valence_channel'])-{'approach_associated','avoidance_associated'}: raise ValueError('unresolved valence channel')
    cfg,raw=config_from_json(args.plasticity_config)
    candidate_sha=sha256_file(args.candidates)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    states={}
    for character in CHARACTERS:
        state=initialize_state(character=character,n_candidates=len(candidates),candidate_sha256=candidate_sha,config=cfg)
        path=args.out_dir/f'{character}.npz'; meta=save_state(path,state,cfg)
        states[character]={
            'path':path.name,'meta_path':path.name+'.json','state_sha256':meta['state_sha256'],
            'generation':0,'matches':0,'update_events':0,
        }
    manifest={
        'schema_version':1,'kind':'canonical-four-character-lineage-bundle','lineage_id':args.lineage_id,
        'characters':list(CHARACTERS),'reward_id':cfg.reward_id,'plasticity_id':raw.get('id'),
        'candidate_sha256':candidate_sha,'config_sha256':cfg.fingerprint(),'candidate_edges':int(len(candidates)),
        'states':states,'learning_performed':False,
        'invariants':{'independent_state_file_per_character':True,'topology_changed':False,'sign_changed':False,'potentiation_allowed':False},
    }
    manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
    manifest['bundle_manifest_payload_sha256']=hashlib.sha256(manifest_bytes).hexdigest()
    (args.out_dir/'bundle-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2,sort_keys=True)); return 0

if __name__=='__main__': raise SystemExit(main())
