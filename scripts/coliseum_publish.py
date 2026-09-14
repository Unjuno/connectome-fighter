#!/usr/bin/env python3
"""Publish tested Coliseum artifacts and an atomic viewer envelope on main.

Only coliseum-v1 assets and named site/data records are writable. Checkpoints
are immutable; only the latest pointer changes. Keep 12 cycles of videos and
all checkpoint archives. Git conflicts retry from current main without force.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

from coliseum_assets import release, select, fetch
from append_training_history import append_history

TAG = 'coliseum-v1'
DATA = ('training-status.json','evaluation-status.json','evaluation-previous.json','coliseum-status.json')


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(*args): subprocess.run(list(args),check=True)


def validate(root):
    pointer=read(root/'checkpoint-pointer.json')
    cycle=read(root/'coliseum-status.json')
    runid='c'+os.environ['GITHUB_RUN_ID']
    if pointer.get('run_id')!=runid or pointer.get('reward_id')!='COLISEUM-v1':
        raise ValueError('publication does not belong to this tested run')
    if cycle.get('status')!='completed' or cycle.get('paired_evaluation') is not True:
        raise ValueError('incomplete paired evaluation')
    for name in ('latest','previous','training'):
        row=cycle[name]
        if row.get('auto_promotion') is not False or row.get('served_by_vercel') is not False:
            raise ValueError('approved inference boundary violation')
    if cycle['latest']['generation']!=cycle['previous']['generation']+1 or cycle['latest']['evaluation']!=cycle['previous']['evaluation']:
        raise ValueError('parent and child evaluation protocols differ')
    if cycle['latest']['evaluation']['protocol']!='coliseum-paired-full-round-v1' or cycle['latest']['evaluation']['round_frame_limit']!=3600:
        raise ValueError('only complete production-length evaluation may publish')
    archive=root/pointer['archive_name']
    if pointer['archive_name']!=f'coliseum-{runid}-checkpoint.tar.gz' or sha(archive)!=pointer['sha256']:
        raise ValueError('checkpoint bytes do not match pointer')
    with tarfile.open(archive, 'r:gz') as tar:
        state_bytes=tar.extractfile('state/GARNET.npz').read()
        meta=json.load(tar.extractfile('state/GARNET.npz.json'))
    state_sha=hashlib.sha256(state_bytes).hexdigest()
    if (meta.get('state_sha256')!=state_sha or meta.get('character')!='GARNET' or meta.get('reward_id')!='COLISEUM-v1'
        or meta.get('generation')!=pointer.get('generation') or pointer.get('state_sha256')!=state_sha
        or cycle['training'].get('state_sha256')!=state_sha or cycle['latest'].get('state_sha256')!=state_sha
        or cycle['training'].get('generation')!=pointer.get('generation') or cycle['latest'].get('generation')!=pointer.get('generation')):
        raise ValueError('checkpoint metadata and public state identity disagree')
    for name in ('latest','previous'):
        row=cycle[name]; filename=row['video']['asset_url'].rsplit('/',1)[1]
        if not re.fullmatch(r'coliseum-c[0-9]+-(before|after)\.mp4',filename) or sha(root/filename)!=row['video']['sha256']:
            raise ValueError('video bytes do not match evaluated state metadata')
    if read(root/'training-status.json')!=cycle['training'] or read(root/'evaluation-status.json')!=cycle['latest'] or read(root/'evaluation-previous.json')!=cycle['previous']:
        raise ValueError('atomic envelope disagrees with individual records')
    return pointer,cycle


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publication',type=Path,required=True);args=p.parse_args()
    if os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('GITHUB_EVENT_NAME')=='pull_request':
        raise ValueError('publication is restricted to trusted main workflows')
    root=args.publication.resolve();pointer,cycle=validate(root)
    existing=release(TAG)
    if existing is None:
        run('gh','release','create',TAG,'--prerelease','--title','Connectome Coliseum: research candidates',
            '--notes','Automated candidate training. No automatic promotion and no claim of proven strength. Recorded paired evaluations; newest 12 video cycles retained. Checkpoints remain immutable.')
        existing=release(TAG)
    elif any(a['name']=='checkpoint-pointer.json' for a in existing['assets']):
        dest=root/'remote-pointer.json'
        fetch(select(existing,'checkpoint-pointer.json'),dest)
        current=read(dest)
        if current['generation'] not in (pointer['generation']-1,pointer['generation']):
            raise ValueError('refusing stale or out-of-order candidate publication')
        if current['generation']==pointer['generation']-1 and cycle['training']['parent']['state_sha256']!=current.get('state_sha256'):
            raise ValueError('checkpoint parent is not the current Coliseum state')
        if current['generation']==pointer['generation'] and current['sha256']!=pointer['sha256']:
            raise ValueError('refusing a same-generation checkpoint fork')
    assets=[root/pointer['archive_name']]+[root/cycle[k]['video']['asset_url'].rsplit('/',1)[1] for k in ('previous','latest')]
    for path in assets:
        matches=[a for a in existing['assets'] if a['name']==path.name]
        if matches:
            if len(matches)!=1 or matches[0].get('digest')!='sha256:'+sha(path):
                raise ValueError('immutable asset collision')
        else:
            run('gh','release','upload',TAG,str(path))
    # Only advance the resume pointer after all corresponding artifacts exist.
    run('gh','release','upload',TAG,str(root/'checkpoint-pointer.json'),'--clobber')
    for attempt in range(3):
        run('git','fetch','origin','main')
        run('git','reset','--hard','origin/main')  # Ephemeral CI checkout only; never force-push.
        Path('site/data').mkdir(parents=True,exist_ok=True)
        for name in DATA: shutil.copy2(root/name,Path('site/data')/name)
        append_history(Path('site/data/training-status.json'),Path('site/data/training-history.json'))
        run('git','config','user.name','github-actions[bot]')
        run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        run('git','add',*[f'site/data/{name}' for name in DATA],'site/data/training-history.json')
        if subprocess.run(['git','diff','--cached','--quiet']).returncode==0: break
        run('git','commit','-m',f'Publish Coliseum generation {pointer["generation"]} paired evaluation [skip ci]')
        if subprocess.run(['git','push','origin','HEAD:main']).returncode==0: break
        time.sleep(attempt+1)
    else: raise RuntimeError('public data push failed; checkpoint remains recoverable by pointer')
    # Never delete checkpoints or assets outside this pipeline's video prefix.
    latest_release=release(TAG)
    videos=[a for a in latest_release['assets'] if re.fullmatch(r'coliseum-c[0-9]+-(before|after)\.mp4',a['name'])]
    run_dates={}
    for asset in videos:
        rid=asset['name'].rsplit('-',1)[0];run_dates[rid]=max(run_dates.get(rid,''),asset['created_at'])
    keep=set(sorted(run_dates,key=run_dates.get,reverse=True)[:12])
    keep.add('coliseum-'+pointer['run_id'])
    for asset in videos:
        if asset['name'].rsplit('-',1)[0] not in keep:
            run('gh','release','delete-asset',TAG,asset['name'],'--yes')
    print(json.dumps({'status':'PUBLISHED','generation':pointer['generation'],'auto_promotion':False}));return 0


if __name__=='__main__':raise SystemExit(main())
