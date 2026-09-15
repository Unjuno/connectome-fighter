#!/usr/bin/env python3
"""Candidate-only fetch, package and publication for one coherent paired cycle.

Remote mutation is restricted to a separate main-only publication job. Immutable
run-addressed assets are uploaded before a single public JSON commit. Retries
never overwrite a newer cycle or force a remote ref. No Vercel/approved writes.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from connectome_fighter.paired_rollout import (ROLLOUT, PROTOCOL_SHA256, digest, file_hash,
    write_json, checked_hash, validate_view, publication_guard, weights_hash, seeds)
from connectome_fighter.paired_search import score_round, COMBAT_REWARD, CURRICULUM_REWARD

REPO = 'Unjuno/connectome-fighter'
VIEW = 'site/data/paired-latest.json'


def command(args: list[str], **kwargs):
    return subprocess.run(args, check=True, timeout=kwargs.pop('timeout', 180), **kwargs)


def api(path: str, *, optional: bool = False):
    p = subprocess.run(['gh', 'api', f'repos/{REPO}/{path}'], capture_output=True, text=True, timeout=60)
    if p.returncode:
        if optional and '(HTTP 404)' in p.stderr:
            return None
        raise RuntimeError(f'GitHub request failed: {p.stderr}')
    return json.loads(p.stdout)


def asset(release: dict, name: str) -> dict:
    matches = [a for a in release['assets'] if a['name'] == name and a['state'] == 'uploaded']
    if len(matches) != 1:
        raise ValueError('missing or ambiguous asset: ' + name)
    a = matches[0]
    if type(a['id']) is not int or a['id'] <= 0 or type(a['size']) is not int or a['size'] <= 0:
        raise ValueError('invalid asset metadata')
    if not re.fullmatch('sha256:[a-f0-9]{64}', a.get('digest', '')):
        raise ValueError('asset digest required')
    return {k: a[k] for k in ('id', 'name', 'size', 'digest')}


def download(a: dict, target: Path) -> None:
    with target.open('wb') as handle:
        command(['gh', 'api', f'repos/{REPO}/releases/assets/{a["id"]}', '-H', 'Accept: application/octet-stream'], stdout=handle)
    if file_hash(target) != a['digest'][7:] or target.stat().st_size != a['size']:
        raise ValueError('downloaded asset does not match selected bytes')


def remote_view() -> dict | None:
    row = api(f'contents/{VIEW}?ref=main', optional=True)
    if row is None:
        return None
    v = json.loads(base64.b64decode(row['content']))
    validate_view(v)
    return v


def fetch_inputs(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    previous = remote_view()
    runtime = asset(api('releases/tags/arena-runtime-latest'), 'arena-runtime.tar.gz')
    if previous is not None:
        source = previous['checkpoint_asset']
        tag = source['release_tag']
        if not re.fullmatch(r'paired-cycle-[0-9]+-[0-9]+', tag) or source['name'] != 'checkpoint.tar.gz':
            raise ValueError('invalid paired checkpoint location')
        checkpoint = asset(api('releases/tags/' + tag), source['name'])
        if checkpoint['digest'] != 'sha256:' + source['sha256'] or checkpoint['size'] != source['size']:
            raise ValueError('checkpoint pointer/asset mismatch')
    else:
        # One explicit fork from R2e. Missing/corrupt R2e must not select a different model.
        release = api('releases/tags/combat-training-v1')
        pointer = asset(release, 'training-manifest.json')
        download(pointer, out / 'seed-manifest.json')
        meta = json.loads((out / 'seed-manifest.json').read_text())
        if meta.get('reward_id') != 'R2e-combat-v1' or meta.get('auto_promotion') is not False:
            raise ValueError('wrong initial seed contract')
        if not re.fullmatch(r'garnet-g[0-9]+-[a-f0-9]{16}\.tar\.gz', meta['archive_file']):
            raise ValueError('invalid seed asset name')
        checkpoint = asset(release, meta['archive_file'])
        if checkpoint['digest'] != 'sha256:' + meta['archive_sha256']:
            raise ValueError('seed pointer/asset mismatch')
    download(runtime, out / 'runtime.tar.gz')
    download(checkpoint, out / 'source.tar.gz')
    write_json(out / 'dependencies.json', {'runtime': runtime, 'checkpoint': checkpoint,
               'previous_view': previous, 'parent_view_sha256': digest(previous) if previous else None})


def read(path: Path):
    return json.loads(path.read_text())


def package(out: Path, *, run_id: str, attempt: str, commit: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit() or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('exact CI run and checkout identities required')
    result, design = read(out / 'result.json'), read(out / 'design.json')
    metadata = read(out / 'candidate/search-state.json')
    if result.get('status') != 'PASS' or result.get('rollout') != ROLLOUT or metadata != result.get('checkpoint'):
        raise ValueError('only completed persistent cycles may publish')
    if design.get('tested_checkout') != commit or design.get('protocol_sha256') != PROTOCOL_SHA256:
        raise ValueError('tested checkout/protocol mismatch')
    if result.get('parent_source_unchanged') is not True or result.get('strength_claim') is not False:
        raise ValueError('source/interpretation boundary failed')
    if file_hash(out / 'candidate/search-state.npz') != metadata['state_file_sha256']:
        raise ValueError('output checkpoint hash mismatch')
    import numpy as np
    with np.load(out / 'candidate/search-state.npz', allow_pickle=False) as state:
        if weights_hash(state['multipliers']) != metadata['weights_sha256']:
            raise ValueError('effective state hash mismatch')
    entries = read(out / 'matches-summary.json')
    if len(entries) != result['completed_games'] or len(entries) < 12:
        raise ValueError('incomplete experiment game list')
    if len({e['name'] for e in entries}) != len(entries):
        raise ValueError('duplicate game names')
    for entry in entries:
        name = entry['name']
        if not re.fullmatch('[a-zA-Z0-9-]+', name):
            raise ValueError('invalid game name')
        folder = out / 'matches' / name
        trace = [json.loads(s) for s in (folder / 'p1.jsonl').read_text().splitlines() if s.strip()]
        samples = [json.loads(s) for s in (folder / 'observed-frames.jsonl').read_text().splitlines() if s.strip()]
        if len(trace) != 1 or score_round(trace[0], samples) != entry['metrics']:
            raise ValueError('score does not match saved raw trace')
        game = read(folder / 'result.json')
        expected = 1 if entry['opponent'] == 'neutral' else 2
        if game.get('status') != 'PASS' or game.get('metrics') != entry['metrics'] or game.get('completed_rounds') != [1, 1]:
            raise ValueError('game completion/metrics mismatch')
        if len(game.get('workers', [])) != expected or not all(w['neurons'] == 156675 and w['synapses'] == 6025920 for w in game['workers']):
            raise ValueError('canonical worker counts mismatch')
        if game.get('policy_pixel_access') is not False or game.get('learning_performed') is not False or game.get('synthetic_neural_fixture') is not False:
            raise ValueError('round boundary mismatch')
    by_name = {e['name']: e for e in entries}
    plan=seeds(metadata['cycle_index'])
    if metadata.get('seed_plan')!=plan or design.get('seed_plan')!=plan or result.get('cycle_index')!=metadata['cycle_index']:
        raise ValueError('cycle/seed plan mismatch')
    if result.get('accepted_update') is not metadata.get('weights_changed') or result.get('parent_weights_sha256')!=metadata['parent_weights_sha256']:
        raise ValueError('result/checkpoint acceptance mismatch')
    training_opponent='neutral' if result['phase']=='curriculum' else 'canonical'
    for entry in entries:
        name=entry['name']
        if name in ('combat-before','combat-after'):
            expected_seed=plan['combat'];expected_opponent='canonical'
        elif name in ('selection-parent','curriculum-proposal'):
            expected_seed=plan['selection'];expected_opponent=training_opponent
        elif name.startswith('validation-'):
            found=re.fullmatch(r'validation-([0-9]+)-(parent|candidate)',name)
            if not found or int(found[1]) not in plan['validation']:
                raise ValueError('unplanned validation condition')
            expected_seed=int(found[1]);expected_opponent=training_opponent
        elif name in ('curriculum-before','curriculum-repeat') or re.fullmatch(r'probe-[0-3]-(plus|minus)',name):
            expected_seed=plan['training'];expected_opponent=training_opponent
        else:raise ValueError('unplanned game')
        game=read(out/'matches'/name/'result.json')
        if entry['seed']!=expected_seed or entry['opponent']!=expected_opponent or game.get('seed_p1')!=expected_seed or game.get('opponent_mode')!=expected_opponent:
            raise ValueError('recorded game does not match the cycle plan')
    from connectome_fighter.paired_search import propose
    score_key='curriculum_score' if result['phase']=='curriculum' else 'combat_score'
    plus=[by_name[f'probe-{j}-plus']['metrics'][score_key] for j in range(4)]
    minus=[by_name[f'probe-{j}-minus']['metrics'][score_key] for j in range(4)]
    gradient,step=propose(design['paired_directions'],plus,minus)
    if plus!=result['plus_scores'] or minus!=result['minus_scores'] or not np.allclose(gradient,result['gradient'],atol=1e-12,rtol=1e-12) or not np.allclose(step,result['proposal_step'],atol=1e-12,rtol=1e-12):
        raise ValueError('reported gradient does not match game scores')
    if not np.any(step) and result['accepted_update']:
        raise ValueError('zero paired signal cannot change weights')
    if result['combat_before']!=by_name['combat-before']['metrics'] or result['combat_after']!=by_name['combat-after']['metrics']:
        raise ValueError('aggregate combat metrics mismatch')
    if by_name['curriculum-before']['metrics']!=by_name['curriculum-repeat']['metrics']:
        raise ValueError('baseline repeatability failed')
    if by_name['combat-before']['multipliers_sha256']!=metadata['parent_weights_sha256'] or by_name['combat-after']['multipliers_sha256']!=metadata['weights_sha256']:
        raise ValueError('evaluated and selected weight identities mismatch')
    if np.any(step):
        a=by_name['selection-parent']['metrics'];b=by_name['curriculum-proposal']['metrics']
        qualifies=b[score_key]>a[score_key]+1e-12
        if result['phase']=='curriculum':qualifies=qualifies and b['damage_dealt_hp']>=a['damage_dealt_hp']
        if result['accepted_update'] and not qualifies:
            raise ValueError('candidate did not pass independent selection')
        if result['accepted_update']:
            for seed in plan['validation']:
                for who in ('parent','candidate'):
                    if f'validation-{seed}-{who}' not in by_name:raise ValueError('validation evidence missing')
    publish = out / 'publish'
    publish.mkdir(exist_ok=False)
    tag = f'paired-cycle-{run_id}-{attempt}'
    root_url = f'https://github.com/{REPO}/releases/download/{tag}'
    run_url = f'https://github.com/{REPO}/actions/runs/{run_id}'
    now = datetime.now(timezone.utc).isoformat()
    protocol = {'protocol': 'paired-rollout-combat-v1', 'rounds': 1, 'fixed_opponent': True,
                'seed_p1': 800101, 'seed_p2': 20202, 'round_frame_limit': 3600,
                'nominal_game_fps': 60, 'configured_round_limit_seconds': 60,
                'decision_interval_frames': 60}
    def evaluation(name, phase, weight_hash, generation):
        item = by_name[name]
        if item['opponent'] != 'canonical' or item['seed'] != 800101:
            raise ValueError('not a fixed canonical combat comparison')
        video = item['video']
        path = out / video['path']
        if path.resolve() != (out / 'matches' / name / 'screen.mp4').resolve():
            raise ValueError('video outside named game')
        if file_hash(path) != video['sha256'] or path.stat().st_size != video['bytes']:
            raise ValueError('recorded video hash mismatch')
        shutil.copy2(path, publish / f'{phase}.mp4')
        m = dict(item['metrics'])
        m.update(winner='GARNET' if m['outcome'] > 0 else 'ZEN' if m['outcome'] < 0 else 'DRAW',
                 elapsed_seconds=m['elapsed_frame'] / 60, ended_by='KO' if min(m['p1_hp'], m['p2_hp']) == 0 else 'TIME_LIMIT')
        return {'schema_version': 2, 'kind': 'post-update-candidate-round-evaluation', 'status': 'COMPLETED',
                'candidate_only': True, 'served_by_vercel': False, 'auto_promotion': False,
                'policy_pixel_access': False, 'character': 'GARNET', 'opponent': 'ZEN',
                'generation': generation, 'state_sha256': weight_hash,
                'state_identity_kind': 'effective-multipliers-float32-le',
                'model': metadata['model'], 'reward_id': COMBAT_REWARD, 'comparison_phase': phase,
                'evaluated_at': now, 'source_training_run_url': run_url, 'evaluation': protocol, 'result': m,
                'video': {'asset_url': root_url + f'/{phase}.mp4', 'sha256': video['sha256'],
                          'bytes': video['bytes'], 'duration_seconds': video['recording_seconds'],
                          'codec': 'h264', 'width': 960, 'height': 640, 'fps': 10},
                'interpretation_boundary': 'Recorded same-seed comparison, not held-out strength or LIVE.'}
    previous = evaluation('combat-before', 'before', metadata['parent_weights_sha256'], metadata['generation'] - int(metadata['weights_changed']))
    latest = evaluation('combat-after', 'after', metadata['weights_sha256'], metadata['generation'])
    with tarfile.open(publish / 'checkpoint.tar.gz', 'w:gz') as archive:
        archive.add(out / 'candidate', arcname='candidate')
    archive_meta = {'release_tag': tag, 'name': 'checkpoint.tar.gz',
                    'sha256': file_hash(publish / 'checkpoint.tar.gz'),
                    'size': (publish / 'checkpoint.tar.gz').stat().st_size}
    training = {'kind': 'canonical-continuous-training-candidate', 'status': 'candidate-only-not-arena-approved',
                'character': 'GARNET', 'generation': metadata['generation'], 'model': metadata['model'],
                'reward_id': CURRICULUM_REWARD if result['phase'] == 'curriculum' else COMBAT_REWARD,
                'updated_at': now, 'served_by_vercel': False, 'auto_promotion': False,
                'state_sha256': metadata['weights_sha256'], 'source_run_url': run_url,
                'matches_this_cycle': result['completed_games'], 'matches': None,
                'cycle_index': metadata['cycle_index'], 'accepted_update_count': metadata['accepted_update_count'],
                'accepted_update': result['accepted_update'], 'update_reason': result['update_reason'],
                'phase': result['phase'], 'next_phase': metadata['next_phase'], 'mastery_streak': metadata['mastery_streak'],
                'requested_interval_minutes': 5, 'actual_pipeline_seconds': result['actual_pipeline_seconds'],
                'combat_metrics': {'before': result['combat_before'], 'after': result['combat_after']},
                'seed_plan': metadata['seed_plan'], 'strength_claim': False}
    prior = read(out / 'dependencies.json')['previous_view']
    history = (prior.get('history', []) if prior else [])[-47:] + [training]
    view = {'schema_version': 1, 'rollout': ROLLOUT, 'protocol_sha256': PROTOCOL_SHA256,
            'ready': True, 'status': 'paired-evaluation-ready', 'cycle_index': metadata['cycle_index'],
            'accepted_update_count': metadata['accepted_update_count'], 'source_run_url': run_url,
            'source_commit': commit, 'updated_at': now, 'parent_view_sha256': digest(prior) if prior else None,
            'latest': latest, 'previous': previous, 'training': training, 'history': history,
            'checkpoint_asset': archive_meta}
    publication_guard(prior, view)
    write_json(publish / 'paired-latest.json', view)
    write_json(publish / 'experiment-result.json', result)
    write_json(publish / 'experiment-design.json', design)
    # Evidence includes real trace records, not only aggregate scores.
    with zipfile.ZipFile(publish / 'trace-evidence.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((out / 'matches').rglob('*')):
            if path.is_file() and path.suffix in ('.json', '.jsonl', '.log'):
                archive.write(path, path.relative_to(out))
        for rel in ('scripts/paired_search_experiment.py', 'scripts/paired_search_game.py',
                    'scripts/paired_rollout_io.py', 'src/connectome_fighter/paired_search.py',
                    'src/connectome_fighter/paired_rollout.py'):
            archive.write(ROOT / rel, 'tested-source/' + rel)
    files = {p.name: {'sha256': file_hash(p), 'size': p.stat().st_size} for p in publish.iterdir() if p.is_file()}
    write_json(publish / 'publication.json', {'run_id': run_id, 'attempt': attempt, 'commit': commit, 'tag': tag, 'files': files})
    return view


def writer_guard(spec: dict, environment: dict) -> None:
    if environment.get('GITHUB_REPOSITORY') != REPO or environment.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('write outside canonical main is forbidden')
    if environment.get('GITHUB_EVENT_NAME') not in ('push', 'schedule', 'workflow_dispatch'):
        raise ValueError('pull requests cannot publish')
    if environment.get('CONNECTOME_TRAINING_PAUSED') == 'true':
        raise ValueError('training publication is paused')
    for field, key in [('run_id', 'GITHUB_RUN_ID'), ('attempt', 'GITHUB_RUN_ATTEMPT'), ('commit', 'GITHUB_SHA')]:
        if spec.get(field) != environment.get(key):
            raise ValueError('publication/run mismatch: ' + field)
    if spec.get('tag') != f"paired-cycle-{spec['run_id']}-{spec['attempt']}":
        raise ValueError('invalid immutable release name')


def publish_view(publish: Path, spec: dict) -> None:
    incoming = read(publish / 'paired-latest.json')
    expected_url = f'https://github.com/{REPO}'
    origin = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip().removesuffix('.git')
    if origin != expected_url:
        raise ValueError('unexpected publication origin')
    for iteration in range(3):
        command(['git', 'fetch', '--no-tags', 'origin', 'main'])
        base = subprocess.check_output(['git', 'rev-parse', 'origin/main'], text=True).strip()
        with tempfile.TemporaryDirectory(prefix='paired-publish-') as tmp:
            work = Path(tmp) / 'checkout'
            command(['git', 'worktree', 'add', '--detach', str(work), base])
            try:
                old = read(work / VIEW) if (work / VIEW).is_file() else None
                if not publication_guard(old, incoming):
                    return
                write_json(work / VIEW, incoming)
                def git(*args):
                    return command(['git', '-C', str(work), *args])
                git('add', VIEW)
                changed = subprocess.check_output(['git', '-C', str(work), 'diff', '--cached', '--name-only'], text=True).splitlines()
                if changed != [VIEW]:
                    raise ValueError('publication touched non-observation files')
                git('-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                    'commit', '-m', 'Publish paired experiment evidence [skip ci]')
                pushed = subprocess.run(['git', '-C', str(work), 'push', 'origin', 'HEAD:main'], timeout=90)
                if pushed.returncode == 0:
                    return
            finally:
                command(['git', 'worktree', 'remove', '--force', str(work)])
        time.sleep(iteration + 1)
    raise RuntimeError('public pointer remained contested; immutable evidence retained, no forced update')


def publish(publish: Path) -> None:
    spec = read(publish / 'publication.json')
    writer_guard(spec, os.environ)
    required = {'paired-latest.json', 'checkpoint.tar.gz', 'before.mp4', 'after.mp4',
                'experiment-result.json', 'experiment-design.json', 'trace-evidence.zip'}
    if set(spec['files']) != required:
        raise ValueError('unexpected publication file set')
    for name, expected in spec['files'].items():
        path = publish / name
        if path.is_symlink() or path.stat().st_size != expected['size'] or file_hash(path) != checked_hash(expected['sha256']):
            raise ValueError('publication artifact hash mismatch')
    incoming = read(publish / 'paired-latest.json')
    publication_guard(remote_view(), incoming)
    tag = spec['tag']
    release = api('releases/tags/' + tag, optional=True)
    if release is None:
        command(['gh', 'release', 'create', tag, '--repo', REPO, '--target', spec['commit'], '--prerelease',
                 '--title', f"Paired experiment cycle {incoming['cycle_index']}",
                 '--notes', 'Actual recorded research comparison. No automatic promotion; no strength claim.'])
        release = api('releases/tags/' + tag)
    existing = {a['name']: a for a in release['assets']}
    for name, expected in spec['files'].items():
        if name in existing:
            a = existing[name]
            if a.get('digest') != 'sha256:' + expected['sha256'] or a['size'] != expected['size']:
                raise ValueError('immutable publication collision')
        else:
            command(['gh', 'release', 'upload', tag, str(publish / name), '--repo', REPO])
    # Check remotely uploaded bytes by provider digest before exposing the view.
    release = api('releases/tags/' + tag)
    for name, expected in spec['files'].items():
        a = asset(release, name)
        if a['digest'] != 'sha256:' + expected['sha256'] or a['size'] != expected['size']:
            raise ValueError('uploaded evidence digest mismatch')
    publish_view(publish, spec)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['fetch', 'package', 'publish'])
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.operation == 'fetch':
        fetch_inputs(args.out)
    elif args.operation == 'package':
        package(args.out, run_id=os.environ['GITHUB_RUN_ID'], attempt=os.environ['GITHUB_RUN_ATTEMPT'], commit=os.environ['GITHUB_SHA'])
    else:
        publish(args.out)

if __name__ == '__main__':
    main()
