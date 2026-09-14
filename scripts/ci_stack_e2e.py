#!/usr/bin/env python3
"""Real functional E2E on CI loopback; not Vercel deployment acceptance.

Actual game, anatomy-based simulated LIF, production publishers and Chromium.
No fabricated neural events, recorded replay, training or cloud allocation.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from verify_live_flybody import ProofError, identity, progressed, same_session, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://127.0.0.1:18000'
EXPECTED_SHA = '9f2df0b8f689b2eccee1d334b6e148854ac949344a9dc6baf57257056734b5e0'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def get(path):
    separator = '&' if '?' in path else '?'
    with urlopen(ORIGIN + path + separator + 'ci=' + str(time.time_ns()), timeout=5) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ProofError('oversized runtime response')
        return raw


def sample(pool):
    state = json.loads(get('/flybody.json'))
    current = json.loads(get('/state'))
    if current.get('status') != 'running':
        raise ProofError('arena not currently running')
    d1 = identity(state['sides']['p1'].get('decision'))
    d2 = identity(state['sides']['p2'].get('decision'))
    if d1[:2] != d2[:2]:
        raise ProofError('physical inputs are not in the same round/frame')
    selector = urlencode({'session_id': current['session_id'], 'round': d1[0], 'frame': d1[1], 'p1': d1[2], 'p2': d2[2]})
    paths = ['/decision-snapshot?' + selector, '/flybody-p1.png', '/flybody-p2.png', '/screen.png', '/activity.json']
    raw = dict(zip(paths, pool.map(get, paths)))
    selected = json.loads(raw[paths[0]])
    if (selected.get('kind') != 'observed-decision-snapshot'
            or selected.get('session_id') != current['session_id']
            or selected.get('selection_mode') != 'observed-decision-history-v1'):
        raise ProofError('invalid observed decision selection')
    live, activity = selected['telemetry'], selected['activity']
    images = {side: raw[paths[i + 1]] for i, side in enumerate(('p1', 'p2'))}
    if live.get('learning_enabled') is not False or live.get('policy_pixel_access') is not False:
        raise ProofError('policy boundary violated')
    metrics = validate_snapshot(live, activity, state, images)
    for side in ('p1', 'p2'):
        brain, command = live['brain'][side], state['sides'][side]['neural_command']
        if not (brain.get('total_spikes', 0) > 0 and brain.get('top_bodies') and command['drive'] > 0
                and command['source_spikes'] > 0 and command['source_body_ids']):
            raise ProofError(side + ': no actual spiking motor input')
        event = selected['source_events'][side]
        digest = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if digest != selected['source_event_sha256'][side] or not 0 <= selected['source_age_seconds'][side] < 30:
            raise ProofError('invalid source hash or expired observed event')
    screen = raw['/screen.png']
    if not (screen[:8] == b'\x89PNG\r\n\x1a\n' and len(screen) > 1000 and struct.unpack('>II', screen[16:24]) == (480, 320)):
        raise ProofError('official ScreenData PNG missing')
    return {'state': state, 'telemetry': live, 'activity': activity, 'selected': selected, 'current': current,
            'images': images, 'screen': screen, 'metrics': metrics,
            'screen_sha256': hashlib.sha256(screen).hexdigest(),
            'endpoints': {'origin': ORIGIN, 'session': live['session_id']}, 'runtime_archive_sha256': EXPECTED_SHA}


def save_sample(out, name, value):
    write_json(out / (name + '.json'), {k: v for k, v in value.items() if k not in ('images', 'screen')})
    for side, raw in value['images'].items():
        (out / (name + '-' + side + '.png')).write_bytes(raw)
    (out / (name + '-screen.png')).write_bytes(value['screen'])


def stop_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM); proc.wait(timeout=10)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=int, default=1200)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true' or os.environ.get('VERCEL'):
        parser.error('standalone CI only')
    if not 60 <= args.timeout_seconds <= 1200:
        parser.error('timeout outside bounded range')
    runtime, out = args.runtime_root.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / 'session'
    manifest = json.loads((runtime / 'manifest.json').read_text())
    assert manifest['canonical_model'] == 'MaleCNS v1.0 + pinned Shiu LIF'
    assert manifest['learning_enabled'] is False and manifest['policy_pixel_access'] is False
    assert manifest['flybody_neural_adapter'] == 'malecns-annotated-motor-to-flybody-tripod-v2'
    assert manifest['brian2_compilerless_reuse_verified'] is True
    assert str(runtime / (runtime / 'runtime/python310.path').read_text().strip()) == manifest['brian2_expected_sys_executable']
    assets = {'data/malecns-shiu-strict-v1/connectivity.parquet': 'adapter_connectivity_sha256',
              'data/interface.json': 'interface_sha256', 'shiu/model.py': 'shiu_model_sha256',
              'fightingice/FightingICE.jar': 'fightingice_jar_sha256'}
    audit = {}
    for path, key in assets.items():
        file_sha = actual = sha(runtime / path)
        if path == 'data/interface.json':
            payload = json.loads((runtime / path).read_text()); embedded = payload.pop('interface_sha256')
            actual = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            assert embedded == actual, 'interface self-hash mismatch'
        audit[path] = {'file_sha256': file_sha, 'manifest_identity_sha256': actual, 'expected': manifest[key], 'match': actual == manifest[key]}
    write_json(out / 'asset-audit.json', audit)
    assert all(row['match'] for row in audit.values()), audit
    for directory in ('src', 'scripts', 'configs'):
        shutil.copytree(ROOT / directory, runtime / 'repo' / directory, dirs_exist_ok=True)
    for source, target in [('start-session.sh', 'start-session'), ('bootstrap-proxy.mjs', 'bootstrap-proxy.mjs')]:
        shutil.copy2(ROOT / 'deploy/arena-runtime' / source, runtime / 'bin' / target)
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for directory in ('src', 'scripts', 'configs', 'app/live', 'deploy/arena-runtime')
                     for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    write_json(out / 'environment.json', {
        'kind': 'ci-real-stack-functional-e2e', 'production_deployment_e2e': False,
        'synthetic_neural_fixture': False, 'recorded_biological_spikes': False, 'simulated_spikes_from_real_connectome': True,
        'training_enabled': False, 'runtime_asset_sha256': EXPECTED_SHA, 'runtime_source_overlay': True,
        'tested_checkout': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': source_hashes, 'render_backend': 'osmesa', 'rounds': 2, 'game_frames_per_round': 600,
        'game_decision_interval_frames': 60, 'game_seeds': [800101, 800202], 'flybody_seeds': [7101, 7202],
        'threads': {k: os.environ.get(k) for k in ('LP_NUM_THREADS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS')},
        'python_harness': sys.version, 'started_at': datetime.now(timezone.utc).isoformat(),
        'boundary': 'Actual observed events are selected by held-input identity from bounded history, not relabeled latest state. Exact ScreenData frame identity, lossless replay and Vercel deployment behavior are not claimed.',
    })
    env = dict(os.environ, CONNECTOME_PUBLIC_BROADCAST='true', CONNECTOME_ROUNDS_PER_SESSION='2',
               CONNECTOME_SESSION_ROOT=str(work), CONNECTOME_POST_FIGHT_SECONDS='5', CONNECTOME_POST_SESSION_SECONDS='5',
               CONNECTOME_FIGHTINGICE_MODE='headless', CONNECTOME_MUJOCO_GL='osmesa', CONNECTOME_CI_RUNTIME_ORIGIN=ORIGIN,
               CC='/bin/false', CXX='/bin/false')
    handles, procs, errors = [], [], Counter()
    deadline = time.monotonic() + args.timeout_seconds
    result = {'status': 'FAIL', 'production_deployment_e2e': False}
    try:
        def launch(command, name):
            handle = (out / (name + '.log')).open('wb'); handles.append(handle)
            proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
            procs.append(proc); return proc
        web = launch(['node', 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', '3000'], 'next')
        for _ in range(60):
            if web.poll() is not None: raise RuntimeError('Next.js exited')
            try:
                with urlopen('http://127.0.0.1:3000/live', timeout=2) as response:
                    if response.status == 200: break
            except (URLError, TimeoutError): time.sleep(0.5)
        else: raise TimeoutError('Next.js startup')
        session = launch(['bash', str(runtime / 'bin/start-session'), '--listen', '18000', '--session-id', 'ci-real-stack', '--p1', 'GARNET', '--p2', 'ZEN'], 'session-entrypoint')
        browser = launch(['node', 'scripts/ci_stack_browser.mjs', str(out), str(args.timeout_seconds)], 'browser')
        first = None
        with ThreadPoolExecutor(max_workers=6) as pool:
            while time.monotonic() < deadline:
                if session.poll() is not None: raise RuntimeError(f'session ended before progressing samples: {session.returncode}; {errors}')
                try:
                    value = sample(pool)
                    if first is None or not same_session(first, value):
                        first = value; save_sample(out, 'aligned-first', first)
                    elif progressed(first, value) and first['screen_sha256'] != value['screen_sha256']:
                        save_sample(out, 'aligned-second', value); break
                except (ProofError, URLError, OSError, ValueError, KeyError) as error:
                    errors[str(error)] += 1; write_json(out / 'sample-error-counts.json', dict(errors))
                time.sleep(0.15)
            else: raise TimeoutError('no progressing aligned samples')
        for proc, name in ((browser, 'browser'), (session, 'session')):
            rc = proc.wait(timeout=max(1, deadline - time.monotonic()))
            if rc != 0: raise RuntimeError(f'{name} failed: {rc}')
        status = json.loads((work / 'live/runs/ci-real-stack/status.json').read_text())
        assert status['status'] == 'COMPLETED_WITH_VALIDATED_CANONICAL_TRACES'
        assert status['learning_performed'] is False and status['trace_trainable'] is False
        assert status['completed_rounds_per_agent'] == [2, 2] and status['live_telemetry_observer_errors'] == [0, 0]
        assert len(status['workers']) == 2 and all(w['neurons'] == 156675 and w['synapses'] == 6025920 for w in status['workers'])
        events = [json.loads(line) for line in (work / 'live/live-decisions.jsonl').read_text().splitlines() if line.strip()]
        by_identity = {(e['side'], e['round_id'], e['frame'], e['brain']['trace_decision_index']): e for e in events if e.get('kind') == 'decision'}
        for name in ('aligned-first', 'aligned-second'):
            record = json.loads((out / (name + '.json')).read_text())
            for side in (1, 2):
                event = record['selected']['source_events'][f'p{side}']
                key = (side, event['round_id'], event['frame'], event['brain']['trace_decision_index'])
                assert by_identity[key] == event, 'HTTP source does not equal independently saved raw event'
        counts = {str(s): sum(key[0] == s for key in by_identity) for s in (1, 2)}
        assert min(counts.values()) >= 2
        result = {'status': 'PASS', 'production_deployment_e2e': False, 'synthetic_neural_fixture': False,
                  'real_game_completed': True, 'source_events_equal_raw_log': True, 'both_sides_progressed': True,
                  'decision_counts': counts, 'browser': json.loads((out / 'browser-proof.json').read_text())}
        assert result['browser']['status'] == 'PASS'
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'; raise
    finally:
        for proc in reversed(procs): stop_group(proc)
        for handle in handles: handle.close()
        result['finished_at'] = datetime.now(timezone.utc).isoformat(); write_json(out / 'result.json', result)
        inputs = work / 'snapshot'
        if inputs.exists(): write_json(out / 'inference-input-hashes.json', {p.name: sha(p) for p in inputs.iterdir() if p.is_file()})
        for path in work.rglob('*') if work.exists() else []:
            if path.is_file() and (path.suffix in ('.npz', '.parquet', '.npy') or path.stat().st_size > 20 * 1024 * 1024): path.unlink()
    print(json.dumps(result)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
