#!/usr/bin/env python3
"""Materialize a valence-gated per-character KC->MBON state into Shiu input.

Only `Excitatory x Connectivity` magnitudes on audited existing KC->MBON rows
are scaled. Row order, pre/post indices, topology, source MaleCNS weights and
signs are preserved. The pinned Shiu model code is untouched.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from connectome_fighter.valence_plasticity import ValencePlasticityConfig, load_state, sha256_file


def hardlink_or_copy(src:Path,dst:Path)->None:
    dst.parent.mkdir(parents=True,exist_ok=True)
    try: os.link(src,dst)
    except OSError: shutil.copy2(src,dst)


def load_config(path:Path)->ValencePlasticityConfig:
    raw=json.loads(path.read_text(encoding='utf-8'))
    return ValencePlasticityConfig(
        learning_rate=float(raw['learning_rate_per_unit_modulatory_signal']),
        eligibility_decay=float(raw['eligibility_decay_per_decision']),
        pair_count_cap=float(raw['pair_count_cap']),
        normalization_percentile=float(raw['normalization_percentile']),
        multiplier_min=float(raw['multiplier_min']),multiplier_max=float(raw['multiplier_max']),
        positive_target=str(raw['positive_signal_target']),negative_target=str(raw['negative_signal_target']),
        reward_id=str(raw['reward_config']),
    )


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-adapter',type=Path,required=True)
    p.add_argument('--candidates',type=Path,required=True)
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--character',required=True)
    p.add_argument('--plasticity-config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    cfg=load_config(args.plasticity_config); cfg.validate()
    c=pd.read_parquet(args.candidates).sort_values('synapse_index').reset_index(drop=True)
    required={'synapse_index','pre_index','post_index','sign','mbon_valence_channel'}
    if not required.issubset(c.columns) or c.empty: raise ValueError('invalid valence candidate table')
    if not (c['sign']==1).all(): raise ValueError('candidate sign invariant failed')
    if set(c['mbon_valence_channel'])-{'approach_associated','avoidance_associated'}: raise ValueError('unresolved valence channels')
    candidate_sha=sha256_file(args.candidates)
    state=load_state(args.state,expected_character=args.character,n_candidates=len(c),expected_candidate_sha256=candidate_sha,config=cfg)

    base_manifest=json.loads((args.base_adapter/'manifest.json').read_text(encoding='utf-8'))
    args.out.mkdir(parents=True,exist_ok=True)
    for name in ['completeness.csv','neuron_metadata.parquet']:
        dst=args.out/name
        if dst.exists(): dst.unlink()
        hardlink_or_copy(args.base_adapter/name,dst)

    candidate_index=c['synapse_index'].to_numpy(dtype=np.int64); multipliers=state.multipliers.astype(np.float64)
    expected_pre_all=c['pre_index'].to_numpy(dtype=np.int64); expected_post_all=c['post_index'].to_numpy(dtype=np.int64)
    src=pq.ParquetFile(args.base_adapter/'connectivity.parquet'); dst_path=args.out/'connectivity.parquet'
    schema=pa.schema([('Presynaptic_Index',pa.int64()),('Postsynaptic_Index',pa.int64()),('Excitatory x Connectivity',pa.float64()),('MaleCNS_Weight',pa.int64())])
    writer=pq.ParquetWriter(dst_path,schema,compression='zstd'); offset=0; visited=0; actually_changed=0
    try:
        for batch in src.iter_batches(batch_size=250_000):
            t=pa.Table.from_batches([batch]); pre=t['Presynaptic_Index'].to_numpy().astype(np.int64,copy=False); post=t['Postsynaptic_Index'].to_numpy().astype(np.int64,copy=False)
            signed=t['Excitatory x Connectivity'].to_numpy().astype(np.float64,copy=True); raw=t['MaleCNS_Weight'].to_numpy().astype(np.int64,copy=False)
            end=offset+len(signed); lo=np.searchsorted(candidate_index,offset,'left'); hi=np.searchsorted(candidate_index,end,'left')
            if hi>lo:
                global_idx=candidate_index[lo:hi]; local=global_idx-offset
                if not np.array_equal(pre[local],expected_pre_all[lo:hi]) or not np.array_equal(post[local],expected_post_all[lo:hi]): raise ValueError('candidate row identity mismatch')
                base=signed[local].copy()
                if np.any(base<=0): raise ValueError('candidate base sign no longer positive')
                signed[local]=base*multipliers[lo:hi]
                if np.any(signed[local]<=0): raise ValueError('materialization changed sign')
                visited+=len(local); actually_changed+=int(np.count_nonzero(np.abs(signed[local]-base)>1e-12))
            writer.write_table(pa.table({'Presynaptic_Index':pre,'Postsynaptic_Index':post,'Excitatory x Connectivity':signed,'MaleCNS_Weight':raw},schema=schema)); offset=end
    finally: writer.close()
    if visited!=len(c): raise RuntimeError(f'visited {visited} candidates, expected {len(c)}')

    manifest=dict(base_manifest); manifest['adapter']='malecns-to-shiu-reference-v1+KC-MBON-valence-depression-v0'; manifest['base_adapter']=base_manifest['adapter']
    manifest['plasticity']={
        'model':'KC-MBON-valence-depression-v0','reward_id':cfg.reward_id,'character':args.character,
        'generation':int(state.generation),'matches':int(state.matches),'update_events':int(state.update_events),
        'candidate_edges':int(len(c)),'materialized_changed_edges':actually_changed,
        'candidate_sha256':candidate_sha,'config_sha256':cfg.fingerprint(),'state_sha256':sha256_file(args.state),
        'multiplier_min':float(state.multipliers.min()),'multiplier_max':float(state.multipliers.max()),'multiplier_mean':float(state.multipliers.mean()),
        'depression_only':True,'topology_changed':False,'sign_changed':False,
    }
    manifest['output_hashes']=dict(base_manifest['output_hashes']); manifest['output_hashes']['connectivity_sha256']=sha256_file(dst_path)
    manifest['interpretation_boundary']='Character-specific R2d-v0 valence-gated project plasticity scales only audited real KC->MBON magnitudes; MaleCNS topology/sign and pinned Shiu dynamics remain unchanged.'
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','character':args.character,'generation':state.generation,'candidate_edges':len(c),'changed_edges':actually_changed,'connectivity_sha256':manifest['output_hashes']['connectivity_sha256']},indent=2,sort_keys=True))
    return 0

if __name__=='__main__': raise SystemExit(main())
