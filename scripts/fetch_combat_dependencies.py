#!/usr/bin/env python3
"""Read-only dependency resolution: pin release asset IDs and byte digests.

Only the explicit Connectome repository is accessed. A missing new experiment
release may seed from the old candidate; other HTTP failures do not select a
fallback. No release creation, upload, deployment or secret operations occur.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

REPO='Unjuno/connectome-fighter'


def api(path, binary=False, output=None):
    cmd=['gh','api',f'repos/{REPO}/{path}']
    if binary:cmd+=['-H','Accept: application/octet-stream']
    if output:
        with Path(output).open('wb') as handle:subprocess.run(cmd,check=True,stdout=handle,timeout=180)
        return None
    return json.loads(subprocess.check_output(cmd,timeout=60))


def asset(release,name):
    rows=[a for a in release['assets'] if a['name']==name and a['state']=='uploaded']
    if len(rows)!=1:raise ValueError(f'expected one uploaded {name}')
    row=rows[0]
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',row.get('digest','')):raise ValueError('asset byte digest missing')
    return row


def download(row,path):
    api(f"releases/assets/{row['id']}",binary=True,output=path)
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(4*1024*1024),b''):h.update(block)
    if h.hexdigest()!=row['digest'][7:] or Path(path).stat().st_size!=row['size']:raise ValueError('asset content changed or download corrupt')


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    release=api('releases/tags/arena-runtime-latest');runtime=asset(release,'arena-runtime.tar.gz')
    attempt=subprocess.run(['gh','api',f'repos/{REPO}/releases/tags/combat-training-v1'],capture_output=True,text=True,timeout=60)
    if attempt.returncode:
        if 'HTTP 404' not in attempt.stderr:raise RuntimeError(attempt.stderr)
        candidate_release=api('releases/tags/canonical-training-latest')
        checkpoint=asset(candidate_release,'garnet-training-latest.tar.gz')
        source_kind='R2d-seed'
    else:
        candidate_release=json.loads(attempt.stdout)
        pointer=asset(candidate_release,'training-manifest.json');download(pointer,args.out/'selected-training-manifest.json')
        manifest=json.loads((args.out/'selected-training-manifest.json').read_text())
        if manifest.get('reward_id')!='R2e-combat-v1':raise ValueError('wrong experiment reward')
        name=manifest['archive_file']
        if not re.fullmatch(r'garnet-g[0-9]+-[a-f0-9]{16}\.tar\.gz',name):raise ValueError('invalid checkpoint asset name')
        checkpoint=asset(candidate_release,name)
        if checkpoint['digest']!='sha256:'+manifest['archive_sha256']:raise ValueError('pointer/archive mismatch')
        source_kind='R2e-resume'
    descriptor={'runtime':{k:runtime[k] for k in ['id','name','digest','size']},'checkpoint':{k:checkpoint[k] for k in ['id','name','digest','size']},'source_kind':source_kind}
    (args.out/'dependencies.json').write_text(json.dumps(descriptor,indent=2)+'\n')
    download(runtime,args.out/'runtime.tar.gz');download(checkpoint,args.out/'source.tar.gz')
    print(json.dumps(descriptor,indent=2))

if __name__=='__main__':main()
