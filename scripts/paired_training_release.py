#!/usr/bin/env python3
"""Resume/publish the isolated paired-training release; no main-branch edits.

Immutable run-addressed files are uploaded first. A single JSON pointer is
replaced last. No R2e, approved-inference, Vercel or billing mutation is permitted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

REPO='Unjuno/connectome-fighter'
EXPERIMENT='paired-neural-training-v1'
POINTER_TAG='paired-training-latest'
HEX=re.compile(r'^[a-f0-9]{64}$')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def call(args):
    return subprocess.run(['gh',*args],text=True,capture_output=True,timeout=180)


def api(path,optional=False):
    p=call(['api',f'repos/{REPO}/{path}'])
    if p.returncode:
        if optional and 'HTTP 404' in p.stderr:return None
        raise RuntimeError('GitHub read failed: '+p.stderr)
    return json.loads(p.stdout)


def asset(release,name):
    rows=[a for a in release['assets'] if a['name']==name and a['state']=='uploaded']
    if len(rows)!=1 or not re.fullmatch(r'sha256:[a-f0-9]{64}',rows[0].get('digest','')):
        raise ValueError('one digest-bearing asset required: '+name)
    return rows[0]


def download(row,path,max_bytes):
    if not 0<row['size']<=max_bytes:raise ValueError('asset outside size budget')
    with path.open('wb') as f:
        subprocess.run(['gh','api',f"repos/{REPO}/releases/assets/{row['id']}",'-H','Accept: application/octet-stream'],stdout=f,check=True,timeout=180)
    if path.stat().st_size!=row['size'] or sha(path)!=row['digest'][7:]:raise ValueError('asset digest/size mismatch')


def current(directory):
    release=api(f'releases/tags/{POINTER_TAG}',optional=True)
    if release is None:return None
    directory.mkdir(parents=True,exist_ok=True)
    a=asset(release,'latest.json');download(a,directory/'latest.json',1024*1024)
    latest=json.loads((directory/'latest.json').read_text())
    if latest.get('experiment')!=EXPERIMENT or latest.get('status')!='PASS':raise ValueError('wrong persistent experiment')
    return latest


def resume(out):
    latest=current(out)
    if latest is None:
        print(json.dumps({'resume':False,'reason':'no paired-training release yet; use verified R2e seed'}));return
    tag=latest.get('release_tag','')
    if not re.fullmatch(r'paired-cycle-[0-9]+-[0-9]+',tag):raise ValueError('invalid immutable tag')
    release=api('releases/tags/'+tag)
    row=asset(release,'search-state.npz')
    if row['digest']!='sha256:'+latest['state']['state_file_sha256']:raise ValueError('pointer/state mismatch')
    download(row,out/'search-state.npz',8*1024*1024)
    print(json.dumps({'resume':True,'cycle':latest['cycle'],'state_sha256':latest['state']['state_file_sha256']}))


def require_publication(summary):
    if (os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main'
        or os.environ.get('GITHUB_EVENT_NAME') not in {'push','schedule','workflow_dispatch'}):
        raise ValueError('publication is restricted to this repository main, never PR')
    if (summary.get('source_commit')!=os.environ.get('GITHUB_SHA') or summary.get('source_run_id')!=os.environ.get('GITHUB_RUN_ID')
        or summary.get('source_run_attempt')!=os.environ.get('GITHUB_RUN_ATTEMPT','1')):
        raise ValueError('tested source/run identity mismatch')
    if (summary.get('status')!='PASS' or summary.get('experiment')!=EXPERIMENT
        or summary.get('auto_promotion') is not False or summary.get('candidate_only') is not True
        or summary.get('strength_claim') is not False or summary.get('parent_source_unchanged') is not True):
        raise ValueError('invalid candidate publication boundary')
    s=summary['state']
    if (type(summary.get('cycle')) is not int or summary['cycle']<1 or summary['cycle']!=s.get('cycle')
        or s.get('parent_cycle')!=s['cycle']-1 or s.get('candidate_only') is not True
        or s.get('auto_promotion') is not False or s.get('production_compatible') is not False
        or s.get('weights_changed') is not summary.get('accepted_update')):
        raise ValueError('candidate counters or state boundaries mismatch')
    if not all(HEX.fullmatch(s.get(k,'')) for k in ['state_file_sha256','weights_sha256','parent_weights_sha256']):
        raise ValueError('state checksum missing')


def require_parent(summary,old):
    s=summary['state']
    if old is None:
        if s['parent_cycle']!=0 or s.get('parent_state_file_sha256') is not None:
            raise ValueError('missing predecessor; refuse silent reset')
        return
    if (old['cycle']!=s['parent_cycle'] or old['state']['state_file_sha256']!=s.get('parent_state_file_sha256')
        or old['state']['weights_sha256']!=s['parent_weights_sha256']
        or old.get('config_sha256')!=summary.get('config_sha256')):
        raise ValueError('stale/forked parent or protocol; refuse overwriting newer state')


def ensure_release(tag):
    data=api('releases/tags/'+tag,optional=True)
    if data is None:
        p=call(['release','create',tag,'--repo',REPO,'--prerelease','--title',tag,
                '--notes','Audited paired neural training candidate. No automatic production promotion.'])
        if p.returncode:raise RuntimeError(p.stderr)
        data=api('releases/tags/'+tag)
    return data


def upload_immutable(tag,path,release):
    existing=[a for a in release['assets'] if a['name']==path.name]
    if existing:
        if len(existing)!=1 or existing[0].get('digest')!='sha256:'+sha(path):
            raise ValueError('immutable publication collision')
        return
    p=call(['release','upload',tag,str(path),'--repo',REPO])
    if p.returncode:raise RuntimeError(p.stderr)


def publish(directory):
    summary=json.loads((directory/'summary.json').read_text());require_publication(summary)
    meta=json.loads((directory/'search-state.json').read_text())
    if meta!=summary['state'] or sha(directory/'search-state.npz')!=meta['state_file_sha256']:
        raise ValueError('exported state metadata/bytes mismatch')
    for name in ['before','after','curriculum']:
        spec=summary['videos'][name];path=directory/(name+'.mp4')
        if spec['path']!=path.name or spec['sha256']!=sha(path) or spec['bytes']!=path.stat().st_size:
            raise ValueError('video hash/size mismatch')
    run=summary['source_run_id'];attempt=summary['source_run_attempt']
    if not re.fullmatch(r'[0-9]+',run) or not re.fullmatch(r'[0-9]+',attempt):raise ValueError('invalid run tag')
    old=current(directory/'predecessor')
    if old and old['cycle']==summary['cycle'] and old['state']['state_file_sha256']==meta['state_file_sha256'] and old['source_run_id']==run:
        print('Identical cycle already published');return
    require_parent(summary,old)
    tag=f'paired-cycle-{run}-{attempt}';release=ensure_release(tag)
    for name in ['search-state.npz','search-state.json','before.mp4','after.mp4','curriculum.mp4','summary.json']:
        upload_immutable(tag,directory/name,release)
    visible=api('releases/tags/'+tag)
    for name in ['search-state.npz','search-state.json','before.mp4','after.mp4','curriculum.mp4','summary.json']:
        if asset(visible,name)['digest']!='sha256:'+sha(directory/name):raise ValueError('uploaded bytes not verified')
    latest=dict(summary,release_tag=tag,source_run_url=f'https://github.com/{REPO}/actions/runs/{run}')
    base=f'https://github.com/{REPO}/releases/download/{tag}/'
    latest['state_url']=base+'search-state.npz';latest['report_url']=base+'summary.json'
    latest['previous_report_url']=old.get('report_url') if old else None
    latest['videos']={k:dict(v,url=base+v['path']) for k,v in summary['videos'].items()}
    # A second parent read catches writers outside the concurrency contract.
    require_parent(summary,current(directory/'prepublish'))
    pointer=directory/'latest.json';pointer.write_text(json.dumps(latest,sort_keys=True,indent=2,allow_nan=False)+'\n')
    ensure_release(POINTER_TAG)
    p=call(['release','upload',POINTER_TAG,str(pointer),'--repo',REPO,'--clobber'])
    if p.returncode:raise RuntimeError(p.stderr)
    check=current(directory/'verified')
    if check!=latest:raise ValueError('published pointer readback differs')
    print(json.dumps({'status':'PUBLISHED','cycle':latest['cycle'],'accepted_updates':meta['accepted_updates'],'weights_changed':meta['weights_changed']}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['resume','publish']);p.add_argument('--directory',type=Path,required=True)
    args=p.parse_args()
    (resume if args.mode=='resume' else publish)(args.directory)
if __name__=='__main__':main()
