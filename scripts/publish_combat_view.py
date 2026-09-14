#!/usr/bin/env python3
"""Publish candidate records from a fresh main worktree, retrying normal pushes.

Only four data files can change. No force-push or remote history rewriting.
Evaluation assets are already published and immutable before this stage runs.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from append_training_history import append_history, validate_status

REPO = 'Unjuno/connectome-fighter'
NAMES = ('training-status.json', 'evaluation-status.json', 'evaluation-previous.json')


def validate_payload(payload: dict) -> dict:
    status = payload['training-status.json']
    validate_status(status)
    if status.get('reward_id') != 'R2e-combat-v1':
        raise ValueError('wrong combat reward')
    if type(status.get('parent_generation')) is not int or status['generation'] != status['parent_generation'] + 1:
        raise ValueError('invalid parent generation')
    for name, phase, generation, digest in (
        ('evaluation-status.json', 'after', status['generation'], status['state_sha256']),
        ('evaluation-previous.json', 'before', status['parent_generation'], status['parent_state_sha256']),
    ):
        e = payload[name]
        if (e.get('comparison_phase') != phase or e.get('generation') != generation
            or e.get('state_sha256') != digest or e.get('status') != 'COMPLETED'
            or e.get('candidate_only') is not True or e.get('auto_promotion') is not False
            or e.get('served_by_vercel') is not False or e.get('policy_pixel_access') is not False
            or e.get('source_training_run_url') != status['source_run_url']):
            raise ValueError('paired evaluation does not bind the candidate')
    if payload['evaluation-status.json']['evaluation'] != payload['evaluation-previous.json']['evaluation']:
        raise ValueError('before/after protocols differ')
    return status


def validate_parent(current: dict, status: dict) -> None:
    validate_status(current)
    identity = (current['generation'], current['state_sha256'])
    allowed = {(status['parent_generation'], status['parent_state_sha256']),
               (status['generation'], status['state_sha256'])}
    if identity not in allowed:
        raise ValueError('public candidate advanced, forked, or has a different parent')


def git(repo: Path, *args: str, check: bool = True):
    return subprocess.run(['git', '-C', str(repo), *args], check=check,
                          capture_output=True, text=True, timeout=60)


def publish(repo: Path, payload: dict, *, before_push=None) -> dict:
    """Three bounded fresh-base attempts; before_push is a local race-test hook."""
    status = validate_payload(payload)
    for attempt in range(3):
        git(repo, 'fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main')
        with tempfile.TemporaryDirectory(prefix='combat-view-') as temp:
            work = Path(temp)/'work'
            git(repo, 'worktree', 'add', '--detach', str(work), 'refs/remotes/origin/main')
            try:
                data = work/'site/data'
                validate_parent(json.loads((data/'training-status.json').read_text()), status)
                for name in NAMES:
                    (data/name).write_text(json.dumps(payload[name], indent=2, sort_keys=True, allow_nan=False)+'\n')
                # Use the tested caller's implementation, not code fetched from a newer head.
                append_history(data/'training-status.json', data/'training-history.json')
                paths = ['site/data/'+n for n in (*NAMES, 'training-history.json')]
                git(work, 'add', '--', *paths)
                if git(work, 'diff', '--cached', '--quiet', check=False).returncode == 0:
                    return {'status':'PASS', 'publication':'already-current', 'attempts':attempt+1}
                changed = set(git(work, 'diff', '--cached', '--name-only').stdout.splitlines())
                if changed - set(paths):
                    raise ValueError('publication touched an unrelated file')
                git(work, '-c', 'user.name=github-actions[bot]', '-c',
                    'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                    'commit', '-m', 'Publish combat candidate and paired evaluation [skip ci]')
                if before_push:
                    before_push(attempt)
                pushed = git(work, 'push', 'origin', 'HEAD:refs/heads/main', check=False)
                if pushed.returncode == 0:
                    return {'status':'PASS', 'generation':status['generation'], 'attempts':attempt+1,
                            'commit':git(work, 'rev-parse', 'HEAD').stdout.strip()}
                print(f'Normal push rejected on attempt {attempt+1}; revalidating fresh main.', file=sys.stderr)
            finally:
                # This worktree is temporary and owned by this function, not a user branch.
                git(repo, 'worktree', 'remove', '--force', str(work))
    raise RuntimeError('publication failed after three fresh-base attempts')


def main():
    if (os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/main'
        or os.environ.get('GITHUB_EVENT_NAME') not in ('push', 'schedule', 'workflow_dispatch')):
        raise RuntimeError('publication requires the authorized main-branch workflow')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    args = p.parse_args()
    spec = json.loads((args.input/'publication.json').read_text())
    if spec.get('source_commit') != os.environ['GITHUB_SHA'] or str(spec.get('source_run_id')) != os.environ['GITHUB_RUN_ID']:
        raise ValueError('publication belongs to another run')
    payload = {name:json.loads((args.input/name).read_text()) for name in NAMES}
    if payload['training-status.json']['source_run_url'] != f"https://github.com/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}":
        raise ValueError('candidate provenance belongs to another run')
    print(json.dumps(publish(ROOT, payload), indent=2))

if __name__ == '__main__':
    main()
