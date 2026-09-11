#!/usr/bin/env python3
"""Build a spectator-only MaleCNS structural annotation index from canonical metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args=p.parse_args()
    meta=pd.read_parquet(args.metadata)
    wanted=['bodyId','superclass','class','subclass','type','instance','somaNeuromere','rootSide','somaSide']
    columns=[c for c in wanted if c in meta.columns]
    if 'bodyId' not in columns or 'superclass' not in columns:
        raise ValueError('canonical metadata lacks bodyId/superclass')
    table=meta[columns].copy().sort_values('bodyId', kind='stable').reset_index(drop=True)
    if table.empty or table['bodyId'].duplicated().any():
        raise ValueError('invalid structural annotation table')
    for c in columns:
        if c!='bodyId': table[c]=table[c].astype('string')
    args.out.mkdir(parents=True, exist_ok=True)
    out=args.out/'body_structure.csv.gz'
    table.to_csv(out,index=False,compression='gzip')
    manifest={
        'schema_version':1,
        'dataset':'male-cns:v1.0',
        'purpose':'spectator-only-structural-index',
        'policy_access':False,
        'bodies':int(len(table)),
        'columns':columns,
        'metadata_sha256':sha256(args.metadata),
        'structure_sha256':sha256(out),
        'interpretation_boundary':(
            'somaNeuromere/rootSide and cell annotations are categorical anatomical metadata. '
            'They are used only for post-hoc visualization and are not neuron coordinates or policy inputs.'
        ),
    }
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
