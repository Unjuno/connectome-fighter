#!/usr/bin/env python3
"""Publish only this main-branch run's validated local candidate artifact.

Checkpoint and video assets are immutable by name. The small rolling manifest
is published last. No Vercel deployment or approved inference is changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

REPO='Unjuno/connectome-fighter'


def gh(*args):return subprocess.run(['gh',*args],check=True,timeout=180)


def ensure_release(tag,title):
    check=subprocess.run(['gh','api',f'repos/{REPO}/releases/tags/{tag}'],capture_output=True,text=True,timeout=30)
    if check.returncode:
        if 'HTTP 404' not in check.stderr:raise RuntimeError(check.stderr)
        gh('release','create',tag,'--repo',REPO,'--target',os.environ['GITHUB_SHA'],'--prerelease','--title',title,'--notes','Experimental research candidate and real frozen before/after evaluations. Not approved LIVE inference.')


def upload_immutable(tag, paths):
    release=json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{tag}'],timeout=30))
    existing={a['name']:a for a in release['assets'] if a['state']=='uploaded'}
    for path in paths:
        digest='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
        if path.name in existing:
            if existing[path.name].get('digest')!=digest:raise ValueError('immutable publication collision')
        else:
            gh('release','upload',tag,'--repo',REPO,str(path))


def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('GITHUB_EVENT_NAME') not in ('push','schedule','workflow_dispatch'):
        raise RuntimeError('publication requires an authorized main-branch run')
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);args=p.parse_args();root=args.input
    spec=json.loads((root/'publication.json').read_text())
    assert spec['source_commit']==os.environ['GITHUB_SHA'] and str(spec['source_run_id'])==os.environ['GITHUB_RUN_ID']
    assert spec['checkpoint_tag']=='combat-training-v1' and spec['video_tag']=='combat-evaluation-'+os.environ['GITHUB_RUN_ID']
    manifest=json.loads((root/'training-manifest.json').read_text())
    assert manifest['reward_id']=='R2e-combat-v1' and manifest['auto_promotion'] is False and manifest['served_by_vercel'] is False
    name=spec['archive_file'];assert re.fullmatch(r'garnet-g[0-9]+-[a-f0-9]{16}\.tar\.gz',name)
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==manifest['archive_sha256']
    existence=subprocess.run(['gh','api',f'repos/{REPO}/releases/tags/combat-training-v1'],capture_output=True,text=True,timeout=30)
    if existence.returncode and 'HTTP 404' not in existence.stderr:raise RuntimeError(existence.stderr)
    old=subprocess.run(['gh','release','download','combat-training-v1','--repo',REPO,'--pattern','training-manifest.json','--output','-'],capture_output=True,text=True,timeout=60)
    if existence.returncode==0 and old.returncode!=0:raise RuntimeError('existing candidate pointer could not be verified')
    if old.returncode==0:
        previous=json.loads(old.stdout)
        if previous['generation']==manifest['generation'] and previous['state_sha256']==manifest['state_sha256']:
            print('Candidate publication already exists; retrying visibility only.')
        else:
            assert previous['generation']==manifest['parent_generation'] and previous['state_sha256']==manifest['parent_state_sha256'], 'candidate parent changed'
    ensure_release(spec['video_tag'],'Combat evaluation '+str(manifest['generation']))
    for phase,filename in [('before','evaluation-previous.json'),('after','evaluation-status.json')]:
        entry=json.loads((root/filename).read_text())
        assert entry['video']['sha256']==hashlib.sha256((root/(phase+'.mp4')).read_bytes()).hexdigest()
        assert entry['auto_promotion'] is False and entry['policy_pixel_access'] is False
    upload_immutable(spec['video_tag'],[root/'before.mp4',root/'after.mp4',root/'evaluation-status.json',root/'evaluation-previous.json'])
    ensure_release('combat-training-v1','Combat reward v1 candidate')
    upload_immutable('combat-training-v1',[root/name])
    gh('release','upload','combat-training-v1','--repo',REPO,str(root/'training-manifest.json'),'--clobber')

if __name__=='__main__':main()
