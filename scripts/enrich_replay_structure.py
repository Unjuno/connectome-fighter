#!/usr/bin/env python3
"""Join spectator-only MaleCNS structural annotations into public replay JSON."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

FIELDS = ["superclass", "class", "subclass", "type", "instance", "somaNeuromere", "rootSide", "somaSide"]


def clean(value: str | None):
    if value is None:
        return None
    value = str(value).strip()
    return None if value in {"", "<NA>", "nan", "None"} else value


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--replay', type=Path, required=True)
    p.add_argument('--status', type=Path, required=True)
    p.add_argument('--structure-index', type=Path, required=True)
    args=p.parse_args()

    replay=json.loads(args.replay.read_text(encoding='utf-8'))
    needed=set()
    for frame in replay.get('frames', []):
        for side in ('p1','p2'):
            for item in ((frame.get(side) or {}).get('brain') or {}).get('top_bodies', []):
                needed.add(int(item['body_id']))

    annotations={}
    with gzip.open(args.structure_index,'rt',encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f)
        for row in reader:
            body=int(row['bodyId'])
            if body not in needed:
                continue
            annotations[body]={k:clean(row.get(k)) for k in FIELDS if k in row}
            annotations[body]={k:v for k,v in annotations[body].items() if v is not None}
            if len(annotations)==len(needed):
                break

    annotated=0
    for frame in replay.get('frames', []):
        for side in ('p1','p2'):
            for item in ((frame.get(side) or {}).get('brain') or {}).get('top_bodies', []):
                meta=annotations.get(int(item['body_id']))
                if meta:
                    item['annotation']=meta
                    annotated += 1
    replay['structural_annotation']={
        'source':'MaleCNS v1.0 canonical metadata',
        'policy_access':False,
        'kind':'categorical-anatomical-annotation',
        'note':'somaNeuromere/rootSide are anatomical categories, not neuron XY coordinates or synaptic loci.',
        'requested_body_ids':len(needed),
        'resolved_body_ids':len(annotations),
        'annotated_top_body_rows':annotated,
    }
    args.replay.write_text(json.dumps(replay,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

    status=json.loads(args.status.read_text(encoding='utf-8'))
    status['structural_visualization']={
        'available': bool(annotations),
        'policy_access': False,
        'kind':'soma-neuromere-and-cell-class-summary',
    }
    args.status.write_text(json.dumps(status,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','requested':len(needed),'resolved':len(annotations),'annotated_rows':annotated},indent=2))
    if needed and len(annotations) < int(0.95*len(needed)):
        raise SystemExit('Too many active body IDs lacked canonical structural metadata')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
