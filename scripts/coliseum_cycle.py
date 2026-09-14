#!/usr/bin/env python3
"""One bounded, candidate-only cycle: parent evaluation -> train -> child evaluation.

No network, releases, deployment, or Git writes happen here. Run this with the
verified runtime's bridge Python/site311. The workflow owns artifact selection
and publication. All three matches use real FightingICE and MaleCNS workers.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from connectome_fighter.coliseum_reward import reward_sequence, validate_config
from connectome_fighter.valence_plasticity import ValencePlasticityConfig, load_state, save_state, sha256_file

PROTOCOL = 'coliseum-paired-full-round-v1'
EVAL_SEEDS = (811001, 812002)


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')


def config(path):
    raw = read(path)
    return ValencePlasticityConfig(
        learning_rate=raw['learning_rate_per_unit_modulatory_signal'],
        eligibility_decay=raw['eligibility_decay_per_decision'], pair_count_cap=raw['pair_count_cap'],
        normalization_percentile=raw['normalization_percentile'], multiplier_min=raw['multiplier_min'],
        multiplier_max=raw['multiplier_max'], positive_target=raw['positive_signal_target'],
        negative_target=raw['negative_signal_target'], reward_id=raw['reward_config'])


def prepare_state(source: Path, target: Path, candidate_sha: str) -> dict:
    """Explicit reward-protocol fork, never a silent restart or source overwrite."""
    meta = read(str(source) + '.json')
    if meta.get('reward_id') not in {'R2d-v0', 'COLISEUM-v1'}:
        raise ValueError('unknown checkpoint reward; explicit migration is required')
    old_config = config(ROOT / 'configs' / ('plasticity_valence_v0.json' if meta['reward_id'] == 'R2d-v0' else 'plasticity_coliseum_v1.json'))
    new_config = config(ROOT / 'configs/plasticity_coliseum_v1.json')
    state = load_state(source, expected_character='GARNET', n_candidates=int(meta['n_candidates']),
                       expected_candidate_sha256=candidate_sha, config=old_config)
    old_weights = state.multipliers.copy()
    parent = {'state_sha256': sha256_file(source), 'metadata_sha256': sha256_file(str(source)+'.json'),
              'generation': state.generation, 'matches': state.matches, 'reward_id': old_config.reward_id,
              'config_sha256': old_config.fingerprint(), 'reward_protocol_fork': old_config.reward_id != new_config.reward_id}
    state.config_sha256 = new_config.fingerprint()
    save_state(target, state, new_config)
    restored = load_state(target, expected_character='GARNET', n_candidates=len(old_weights),
                          expected_candidate_sha256=candidate_sha, config=new_config)
    if not np.array_equal(old_weights, restored.multipliers) or sha256_file(source) != parent['state_sha256']:
        raise RuntimeError('fork altered weights or source state')
    return parent


def combat(row):
    final = row['remaining_hps']
    transitions = row['transitions']
    actions = Counter(t.get('action_name', str(t.get('action'))) for t in transitions)
    return {'damage_dealt_hp': 400 - final[1], 'damage_taken_hp': 400 - final[0],
            'no_damage_draw': final == [400, 400], 'decisions': len(transitions), 'selected_action_counts': dict(actions)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root', type=Path, required=True)
    p.add_argument('--source-archive', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    args = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', args.run_id):
        p.error('invalid run identity')
    root, out = args.runtime_root.absolute(), args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    reward_path = ROOT / 'configs/reward_coliseum_v1.json'
    plastic_path = ROOT / 'configs/plasticity_coliseum_v1.json'
    reward = read(reward_path); validate_config(reward)
    candidates = root / 'data/malecns-valence-v1/kc_mbon_valence_candidates.parquet'
    base = root / 'data/malecns-shiu-strict-v1'
    bridge = root / (root / 'runtime/python311.path').read_text().strip()
    reference = root / (root / 'runtime/python310.path').read_text().strip()
    java = root / 'runtime/jre21/bin/java'
    for required in [candidates, base/'connectivity.parquet', bridge, reference, java, root/'shiu/model.py']:
        if not required.is_file():
            raise FileNotFoundError(required)
    wrapper = out / 'reference-python'
    import shlex
    wrapper.write_text('#!/bin/sh\nexport PYTHONPATH=' + shlex.quote(str(root/'runtime/site310')) + '\nexec ' + shlex.quote(str(reference)) + ' "$@"\n')
    wrapper.chmod(0o755)
    env = dict(os.environ, PYTHONPATH=f'{ROOT / "src"}:{root / "runtime/site311"}',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', LP_NUM_THREADS='1')
    source_dir = out/'source'; source_dir.mkdir()
    with tarfile.open(args.source_archive, 'r:gz') as archive:
        archive.extractall(source_dir, filter='data')
    state = out/'checkpoint/state/GARNET.npz'
    parent = prepare_state(source_dir/'state/GARNET.npz', state, sha256_file(candidates))
    write(out/'parent.json', parent)
    generation = parent['generation'] + 1
    opponent = ('ZEN', 'LUD', 'NEZ')[(generation-1) % 3]
    training_seeds = (900000 + generation*17, 900001 + generation*17)
    source_provenance = {
        'runtime': read(root/'manifest.json'), 'source_commit': os.environ.get('SOURCE_COMMIT'),
        'reward_sha256': sha256_file(reward_path), 'plasticity_sha256': sha256_file(plastic_path),
        'parent': parent, 'started_at': now(), 'training_seeds': training_seeds, 'evaluation_seeds': EVAL_SEEDS,
        'control_protocol': PROTOCOL, 'scheduler_target_minutes': 10, 'auto_promotion': False,
    }
    write(out/'provenance.json', source_provenance)
    def command(parts, log, timeout=1200):
        remaining = 1800 - (time.monotonic() - start)
        if remaining <= 0:
            raise TimeoutError('cycle compute budget exhausted')
        with Path(log).open('ab') as stream:
            subprocess.run([str(x) for x in parts], env=env, stdout=stream, stderr=subprocess.STDOUT,
                           check=True, timeout=min(timeout, remaining))
    def materialize(destination):
        command([bridge, ROOT/'scripts/materialize_malecns_valence_adapter.py', '--base-adapter', base,
                 '--candidates', candidates, '--state', state, '--character', 'GARNET',
                 '--plasticity-config', plastic_path, '--out', destination], out/'materialize.log')
    adapter_before = out/'adapter-before'; materialize(adapter_before)
    cfg = reward['control']
    def match(label, adapter, opponent_name, seeds, trainable, record):
        runid = args.run_id + '-' + label
        match_dir = out/label; match_dir.mkdir()
        game_dir = root/'fightingice'
        log = (match_dir/'game.log').open('wb')
        proc = subprocess.Popen([str(java), '-cp', 'FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*',
                                 'Main', '--headless-mode', '--pyftg-mode', '--input-sync', '--limithp', '400', '400',
                                 '--port', '31415', '-r', '1', '-f', str(cfg['round_frame_limit'])],
                                 cwd=game_dir, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError('FightingICE exited before socket startup')
                if 'Socket server is started' in (match_dir/'game.log').read_text(errors='replace'):
                    break
                time.sleep(0.2)
            else:
                raise TimeoutError('FightingICE socket startup timed out')
            parts = [bridge, ROOT/'scripts/run_game_malecns_lif.py', '--host', '127.0.0.1', '--port', '31415',
                     '--character-p1', 'GARNET', '--character-p2', opponent_name,
                     '--seed-p1', str(seeds[0]), '--seed-p2', str(seeds[1]), '--reference-python', wrapper,
                     '--reference-model', root/'shiu/model.py', '--worker-script', root/'repo/scripts/malecns_lif_worker.py',
                     '--adapter-dir', base, '--adapter-dir-p1', adapter, '--adapter-dir-p2', base,
                     '--interface', root/'data/interface.json', '--decision-interval', str(cfg['decision_interval_frames']),
                     '--games', '1', '--expected-rounds', '1', '--timeout', '1000', '--run-id', runid, '--out', match_dir]
            if trainable: parts += ['--trainable-trace']
            if record: parts += ['--spectator-video', out/(label+'.mp4'), '--spectator-fps', '10']
            state_sha_before = sha256_file(state)
            command(parts, match_dir/'runner.log', timeout=1100)
            status = read(match_dir/runid/'status.json')
            if (status.get('status') != 'COMPLETED_WITH_VALIDATED_CANONICAL_TRACES' or status.get('learning_performed') is not False
                or status.get('trace_trainable') is not trainable or status.get('completed_rounds_per_agent') != [1, 1]):
                raise RuntimeError('match audit failed')
            if sha256_file(state) != state_sha_before:
                raise RuntimeError('weights changed during a round')
            rows = [json.loads(x) for x in (match_dir/runid/'p1.jsonl').read_text().splitlines() if x]
            if len(rows) != 1 or rows[0].get('terminated') is not True or rows[0].get('truncated') is not False:
                raise ValueError('not one complete audited round')
            row = rows[0]
            if min(row['remaining_hps']) > 0 and row['elapsed_frame'] != cfg['round_frame_limit']:
                raise ValueError('incomplete non-KO round')
            if record:
                command(['ffprobe','-v','error','-show_entries','format=duration,size','-show_entries','stream=width,height,codec_name',
                         '-of','json', out/(label+'.mp4')], out/(label+'-probe.json'), timeout=30)
            return row, match_dir/runid
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=5)
            log.close()
    before, _ = match('before', adapter_before, 'ZEN', EVAL_SEEDS, False, True)
    before_meta = read(str(state)+'.json')
    train, train_dir = match('train', adapter_before, opponent, training_seeds, True, False)
    reward_sequence(train, 0, reward)  # Reject malformed/incomplete data before writes.
    command([bridge, ROOT/'scripts/update_malecns_valence_plasticity.py', '--character','GARNET','--side','1',
             '--round-trace',train_dir/'p1.jsonl','--spikes',train_dir/'p1-brain/spikes.parquet','--candidates',candidates,
             '--reward-config',reward_path,'--plasticity-config',plastic_path,'--state',state,'--out-summary',out/'update.json'],out/'update.log')
    update = read(out/'update.json'); after_meta = read(str(state)+'.json')
    if update['status'] != 'PASS' or after_meta['generation'] != generation or after_meta['matches'] != parent['matches']+1:
        raise RuntimeError('candidate state did not advance exactly once')
    if update['updates']['potentiated_edges'] != 0 or update['invariants']['topology_changed'] or update['invariants']['sign_changed']:
        raise RuntimeError('plasticity boundary violated')
    adapter_after = out/'adapter-after'; materialize(adapter_after)
    after, _ = match('after', adapter_after, 'ZEN', EVAL_SEEDS, False, True)
    release_base = 'https://github.com/Unjuno/connectome-fighter/releases/download/coliseum-v1'
    def evaluation(label, row, meta):
        video_path = out/(label+'.mp4'); probe = read(out/(label+'-probe.json'))
        stream = probe['streams'][0]; duration = float(probe['format']['duration'])
        if stream.get('codec_name') != 'h264' or (stream.get('width'), stream.get('height')) != (960,640) or not 0 < duration < 120:
            raise RuntimeError('evaluation video is invalid')
        if video_path.stat().st_size < 10000:
            raise RuntimeError('evaluation video is empty')
        final = row['remaining_hps']
        filename = f'coliseum-{args.run_id}-{label}.mp4'
        return {'schema_version':2, 'kind':'post-update-candidate-round-evaluation', 'status':'COMPLETED',
                'candidate_only':True, 'served_by_vercel':False, 'auto_promotion':False, 'policy_pixel_access':False,
                'generation':meta['generation'], 'matches':meta['matches'], 'model':meta['model'], 'reward_id':meta['reward_id'],
                'state_sha256':meta['state_sha256'], 'evaluated_at':now(), 'character':'GARNET','opponent':'ZEN',
                'source_training_run_url':os.environ.get('RUN_URL'), 'comparison_role':'parent-before-update' if label=='before' else 'child-after-update',
                'evaluation':{'protocol':PROTOCOL,'rounds':1,'fixed_opponent':True,'seed_p1':EVAL_SEEDS[0],'seed_p2':EVAL_SEEDS[1],
                              'round_frame_limit':cfg['round_frame_limit'],'nominal_game_fps':60,'configured_round_limit_seconds':60,
                              'decision_interval_frames':cfg['decision_interval_frames'],'opponent_connectivity_sha256':sha256_file(base/'connectivity.parquet')},
                'result':{'winner':'GARNET' if final[0]>final[1] else 'ZEN' if final[0]<final[1] else 'DRAW',
                          'p1_hp':final[0], 'p2_hp':final[1], 'elapsed_frame':row['elapsed_frame'],
                          'elapsed_seconds':row['elapsed_frame']/60,'ended_by':'KO' if min(final)<=0 else 'TIME_LIMIT'},
                'combat':combat(row), 'video':{'asset_url':release_base+'/'+filename,'sha256':sha256_file(video_path),
                           'codec':'h264','width':960,'height':640,'fps':10,'duration_seconds':duration,'bytes':video_path.stat().st_size},
                'interpretation_boundary':'Recorded paired diagnostic, not LIVE or statistical proof of stronger play. Parent/child use identical evaluation seeds, baseline opponent and control protocol. Neural and FlyBody frames are not recorded in these videos.'}
    latest, previous = evaluation('after',after,after_meta), evaluation('before',before,before_meta)
    training = {'schema_version':1,'kind':'canonical-continuous-training-candidate','status':'candidate-only-not-arena-approved',
                'character':'GARNET','opponent':opponent,'generation':generation,'matches':after_meta['matches'],
                'state_sha256':after_meta['state_sha256'],'model':after_meta['model'],'reward_id':'COLISEUM-v1',
                'source_kind':'explicit-reward-protocol-fork' if parent['reward_protocol_fork'] else 'rolling-coliseum-candidate',
                'source_run_url':os.environ.get('RUN_URL'),'served_by_vercel':False,'auto_promotion':False,
                'match_status':'COMPLETED_WITH_VALIDATED_CANONICAL_TRACES','updated_at':now(),
                'signal_summary':update['signals'],'update_summary':update['updates'],'parent':parent,
                'scheduler_interval_minutes':10,'control_protocol':PROTOCOL,'training_seeds':training_seeds,
                'combat':combat(train), 'cycle_wall_seconds':time.monotonic()-start,
                'interpretation_boundary':update['interpretation_boundary']}
    publication = out/'publication'; publication.mkdir()
    write(publication/'evaluation-status.json',latest);write(publication/'evaluation-previous.json',previous)
    write(publication/'training-status.json',training)
    write(publication/'coliseum-status.json', {'schema_version':1,'kind':'coliseum-cycle-status','status':'completed',
          'target_interval_minutes':10,'timing_guarantee':False,'updated_at':now(),'latest':latest,'previous':previous,
          'training':training,'strength_claim':'UNPROVEN','paired_evaluation':True,'run_url':os.environ.get('RUN_URL')})
    archive = publication/f'coliseum-{args.run_id}-checkpoint.tar.gz'
    write(out/'checkpoint/parent.json', parent)
    write(out/'checkpoint/training-manifest.json',training)
    with tarfile.open(archive,'w:gz') as tar:
        for path in sorted((out/'checkpoint').rglob('*')):
            if path.is_file(): tar.add(path,arcname=str(path.relative_to(out/'checkpoint')))
    write(publication/'checkpoint-pointer.json',{'schema_version':1,'archive_name':archive.name,'sha256':sha256_file(archive),
                                               'generation':generation,'reward_id':'COLISEUM-v1','run_id':args.run_id,'state_sha256':after_meta['state_sha256']})
    for label, ev in [('before',previous),('after',latest)]:
        shutil.copy2(out/(label+'.mp4'), publication / ev['video']['asset_url'].rsplit('/',1)[1])
    write(out/'result.json', {'status':'PASS','generation':generation,'parent':parent,
                            'before':previous['combat'],'after':latest['combat'],'cycle_wall_seconds':time.monotonic()-start,
                            'learning_performed':True,'production_promotion':False})
    print(json.dumps(read(out/'result.json'),indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
