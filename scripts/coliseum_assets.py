#!/usr/bin/env python3
"""Resolve exact public GitHub asset IDs and verify bytes before using them.

Requires gh and its standard GH_TOKEN environment. This script only reads
releases. Missing Coliseum state falls back to the explicitly named legacy
candidate only on HTTP 404, never on a transient server/authentication failure.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
import os

REPO = 'Unjuno/connectome-fighter'
SHA = re.compile(r'^[a-f0-9]{64}$')
NAME = re.compile(r'^coliseum-c[0-9]+-checkpoint\.tar\.gz$')


def release(tag):
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}',
          headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'], 'Accept':'application/vnd.github+json', 'User-Agent':'connectome-coliseum/1'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        raise


def select(release_json, name):
    assets = [x for x in release_json['assets'] if x['name'] == name and x['state'] == 'uploaded']
    if len(assets) != 1: raise ValueError(f'missing or ambiguous asset: {name}')
    obj = assets[0]; digest = obj.get('digest', '')
    if not digest.startswith('sha256:') or not SHA.fullmatch(digest[7:]):
        raise ValueError('GitHub asset digest is required')
    return {'id':obj['id'], 'name':name, 'sha256':digest[7:], 'size':obj['size']}


def fetch(obj, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        tmp = path.with_suffix('.download')
        with tmp.open('wb') as output:
            subprocess.run(['gh','api',f'repos/{REPO}/releases/assets/{int(obj["id"])}','-H','Accept: application/octet-stream'],
                           stdout=output, check=True, timeout=240)
        tmp.replace(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024), b''): h.update(block)
    if h.hexdigest() != obj['sha256'] or path.stat().st_size != obj['size']:
        raise ValueError('selected asset byte identity mismatch')
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    runtime=release('arena-runtime-latest')
    if runtime is None: raise RuntimeError('runtime release missing')
    r=select(runtime,'arena-runtime.tar.gz')
    current=release('coliseum-v1')
    if current is None:
        legacy=release('canonical-training-latest')
        if legacy is None: raise RuntimeError('no verified candidate seed; unity fallback is forbidden')
        c=select(legacy,'garnet-training-latest.tar.gz');source='legacy-r2d-fork'
    else:
        pointer_path=fetch(select(current,'checkpoint-pointer.json'),out/'checkpoint-pointer.json')
        pointer=json.loads(pointer_path.read_text())
        if pointer.get('reward_id')!='COLISEUM-v1' or not NAME.fullmatch(str(pointer.get('archive_name',''))):
            raise ValueError('invalid checkpoint pointer')
        c=select(current,pointer['archive_name']);source='coliseum-v1-resume'
        if c['sha256']!=pointer.get('sha256'): raise ValueError('checkpoint pointer/digest mismatch')
    selection={'runtime':r,'checkpoint':c,'source':source}
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    fetch(r,out/'runtime.tar.gz');fetch(c,out/'checkpoint.tar.gz')
    print(json.dumps(selection,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
