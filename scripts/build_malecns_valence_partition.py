#!/usr/bin/env python3
"""Partition real MaleCNS KC->MBON edges into literature-linked MBON valence channels.

No synapse is changed. The partition is an analysis/model adapter derived from
post-synaptic MBON transmitter identity:
- glutamatergic MBON -> avoidance-associated channel
- GABAergic or cholinergic MBON -> approach-associated channel
- anything else -> unresolved

The mapping follows the population-level correlation reported by Aso et al.
2014 (eLife 3:e04580). It is a project model abstraction, not a claim that every
individual MBON has a context-independent scalar valence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

VALENCE_BY_MBON_NT = {
    "glutamate": "avoidance_associated",
    "gaba": "approach_associated",
    "acetylcholine": "approach_associated",
}


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--connectivity',type=Path,required=True)
    p.add_argument('--adapter-manifest',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    args=p.parse_args()

    meta=pd.read_parquet(args.metadata)
    required={'bodyId','Shiu_Index','class','type','resolved_nt','shiu_sign'}
    if not required.issubset(meta.columns):
        raise ValueError(f'metadata missing {sorted(required-set(meta.columns))}')
    meta=meta.sort_values('Shiu_Index').reset_index(drop=True)
    if not np.array_equal(meta['Shiu_Index'].to_numpy(),np.arange(len(meta))):
        raise ValueError('Shiu_Index must be dense and sorted')
    classes=meta['class'].astype('string').fillna('').to_numpy()
    kc=np.flatnonzero(classes=='Kenyon_Cell')
    mbon=np.flatnonzero(classes=='MBON')
    if len(kc)==0 or len(mbon)==0:
        raise ValueError('expected KC and MBON classes')
    kc_set=set(kc.tolist()); mbon_set=set(mbon.tolist())

    rows=[]; global_row=0
    parquet=pq.ParquetFile(args.connectivity)
    for batch in parquet.iter_batches(batch_size=250_000):
        table=pa.Table.from_batches([batch])
        pre=table['Presynaptic_Index'].to_numpy(); post=table['Postsynaptic_Index'].to_numpy()
        signed=table['Excitatory x Connectivity'].to_numpy(); raw=table['MaleCNS_Weight'].to_numpy()
        selected=np.flatnonzero(np.isin(pre,list(kc_set)) & np.isin(post,list(mbon_set)))
        for local in selected.tolist():
            pi=int(pre[local]); po=int(post[local])
            pm=meta.iloc[pi]; qm=meta.iloc[po]
            post_nt=str(qm['resolved_nt']).strip().lower()
            rows.append({
                'synapse_index':int(global_row+local),
                'pre_index':pi,'post_index':po,
                'body_pre':int(pm['bodyId']),'body_post':int(qm['bodyId']),
                'type_pre':None if pd.isna(pm['type']) else str(pm['type']),
                'type_post':None if pd.isna(qm['type']) else str(qm['type']),
                'resolved_nt_pre':str(pm['resolved_nt']),
                'resolved_nt_post':post_nt,
                'mbon_valence_channel':VALENCE_BY_MBON_NT.get(post_nt,'unresolved'),
                'sign':int(np.sign(signed[local])),
                'base_signed_connectivity':int(signed[local]),
                'base_malecns_weight':int(raw[local]),
            })
        global_row += len(pre)

    c=pd.DataFrame(rows)
    if c.empty or c['synapse_index'].duplicated().any():
        raise RuntimeError('invalid KC->MBON candidate extraction')
    if not (c['sign']==1).all():
        raise RuntimeError('KC->MBON incoming candidate sign invariant failed')

    args.out_dir.mkdir(parents=True,exist_ok=True)
    out=args.out_dir/'kc_mbon_valence_candidates.parquet'
    c.to_parquet(out,index=False,compression='zstd')
    adapter=json.loads(args.adapter_manifest.read_text(encoding='utf-8'))
    channel_counts=c['mbon_valence_channel'].value_counts().to_dict()
    nt_counts=c['resolved_nt_post'].value_counts().to_dict()
    unique_mbon_channels=(c[['body_post','mbon_valence_channel']].drop_duplicates()
                          ['mbon_valence_channel'].value_counts().to_dict())
    manifest={
        'schema_version':1,
        'dataset':adapter['dataset'],
        'partition':'KC-to-MBON-by-post-MBON-transmitter-valence-v1',
        'source_literature':{
            'citation':'Aso et al. 2014, eLife 3:e04580',
            'doi':'10.7554/eLife.04580',
            'rule':'glutamatergic MBON activation was avoidance-associated; GABAergic/cholinergic MBON activation was attraction-associated at population level',
        },
        'counts':{
            'kc_to_mbon_edges':int(len(c)),
            'unique_kc':int(c['body_pre'].nunique()),
            'unique_mbon':int(c['body_post'].nunique()),
            'edges_by_channel':{str(k):int(v) for k,v in channel_counts.items()},
            'unique_mbons_by_channel':{str(k):int(v) for k,v in unique_mbon_channels.items()},
            'edges_by_post_transmitter':{str(k):int(v) for k,v in nt_counts.items()},
        },
        'hashes':{
            'metadata_sha256':sha256(args.metadata),
            'connectivity_sha256':sha256(args.connectivity),
            'adapter_manifest_sha256':sha256(args.adapter_manifest),
            'candidate_sha256':sha256(out),
        },
        'invariants':{
            'topology_changed':False,
            'weights_changed':False,
            'signs_changed':False,
            'learning_applied':False,
        },
        'interpretation_boundary':(
            'The valence labels are a literature-linked modeling partition for later experiments. '
            'They do not imply that every MBON has a fixed context-independent scalar valence, '
            'and they are not an annotation field supplied by MaleCNS.'
        ),
    }
    (args.out_dir/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
