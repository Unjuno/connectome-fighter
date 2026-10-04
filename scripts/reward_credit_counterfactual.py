#!/usr/bin/env python3
"""Controlled Gen49 reward-credit counterfactual on the rejected run-2310 seed.

The experiment regenerates the exact no-damage training round from the frozen
Gen49 parent, reproduces the canonical R2e proposal byte-for-byte, then changes
only the reward identifier and zero-damage terminal penalty for R2f. Both
proposals are evaluated on the existing fixed ZEN/LUD/NEZ selection suite.
Nothing here publishes a checkpoint or changes canonical continuous learning.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from connectome_fighter.combat_reward import paired_evaluation_suite_gate

CANONICAL_REWARD = 'R2e-combat-v1'
TREATMENT_REWARD = 'R2f-combat-nodamage-neutral-v0'
READOUT_MODE = 'ema-residual'
READOUT_CONTRACT = 'malecns-temporal-readout-v1'
MATCH_STATUS = 'COMPLETED_WITH_VALIDATED_EXPERIMENTAL_READOUT_TRACES'

PARENT_GENERATION = 49
PARENT_STATE_SHA256 = 'a5c2394d69eecba27c971688dcb88f7992ab872331d8d18d4d9a295d75c4b0fe'
CONTROL_PROPOSAL_SHA256 = 'bc602d637758c28c107f029e55d7732524a9ebe926ed0b73ad8f7aa687c97027'
SOURCE_RUN_ID = 37194195086
SOURCE_RUN_NUMBER = 2310
TRAINING_CASE = {'opponent': 'NEZ', 'seed_p1': 1000036, 'seed_p2': 990306}
VALIDATION_SUITE = (
    {'case_id': 'zen-validation-v1', 'opponent': 'ZEN', 'seed_p1': 810101, 'seed_p2': 31001},
    {'case_id': 'lud-validation-v1', 'opponent': 'LUD', 'seed_p1': 810202, 'seed_p2': 31002},
    {'case_id': 'nez-validation-v1', 'opponent': 'NEZ', 'seed_p1': 810303, 'seed_p2': 31003},
)
EXPECTED_CONTROL_GATE_DELTA = -0.10416666666666696


def sha(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path: str | Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        except ProcessLookupError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--parent-archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=int, default=1400)
    args = parser.parse_args()

    if os.environ.get('CI') != 'true' or os.environ.get('VERCEL'):
        parser.error('standalone CI only')
    if not 600 <= args.timeout_seconds <= 1800:
        parser.error('timeout must be 600..1800 seconds')

    runtime = args.runtime_root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.timeout_seconds

    manifest = json.loads((runtime / 'manifest.json').read_text())
    assert manifest['canonical_model'] == 'MaleCNS v1.0 + pinned Shiu LIF'
    assert manifest['learning_enabled'] is False
    assert manifest['policy_pixel_access'] is False
    assert manifest['brian2_compilerless_reuse_verified'] is True

    ref = runtime / (runtime / 'runtime/python310.path').read_text().strip()
    bridge = runtime / (runtime / 'runtime/python311.path').read_text().strip()
    for name in ('src', 'scripts', 'configs'):
        shutil.copytree(ROOT / name, runtime / 'repo' / name, dirs_exist_ok=True)

    env = dict(
        os.environ,
        PYTHONPATH=f"{runtime / 'repo/src'}:{runtime / 'runtime/site311'}",
        PATH=f"{runtime / 'runtime/jre21/bin'}:{os.environ['PATH']}",
        OMP_NUM_THREADS='1',
        OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1',
    )
    wrapper = out / 'reference-python'
    wrapper.write_text(
        '#!/bin/sh\nexport PYTHONPATH=' + shlex.quote(str(runtime / 'runtime/site310')) +
        '\nexec ' + shlex.quote(str(ref)) + ' "$@"\n'
    )
    wrapper.chmod(0o755)

    def run(command: list, name: str) -> None:
        with (out / f'{name}.log').open('wb') as log:
            proc = subprocess.Popen(
                [str(value) for value in command],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                rc = proc.wait(timeout=max(1, deadline - time.monotonic()))
                if rc:
                    raise RuntimeError(f'{name} exited {rc}; see {name}.log')
            finally:
                stop(proc)

    package = out / 'parent-package'
    package.mkdir()
    with tarfile.open(args.parent_archive) as archive:
        archive.extractall(package, filter='data')
    parent_state = package / 'state/GARNET.npz'
    parent_meta = json.loads(parent_state.with_suffix('.npz.json').read_text())
    assert parent_meta['generation'] == PARENT_GENERATION
    assert parent_meta['reward_id'] == CANONICAL_REWARD
    assert parent_meta['model'] == 'KC-MBON-valence-depression-v0'
    assert sha(parent_state) == parent_meta['state_sha256'] == PARENT_STATE_SHA256

    base = runtime / 'data/malecns-shiu-strict-v1'
    candidates = runtime / 'data/malecns-valence-v1/kc_mbon_valence_candidates.parquet'
    control_cfg = ROOT / 'configs/plasticity_combat_v1.json'
    treatment_cfg = ROOT / 'configs/plasticity_combat_r2f_v0.json'
    control_reward = ROOT / 'configs/reward_r2e_combat_v1.json'
    treatment_reward = ROOT / 'configs/reward_r2f_nodamage_neutral_v0.json'

    def materialize(label: str, state: Path, config: Path) -> Path:
        adapter = out / f'adapter-{label}'
        run([
            bridge,
            runtime / 'repo/scripts/materialize_malecns_valence_adapter.py',
            '--base-adapter', base,
            '--candidates', candidates,
            '--state', state,
            '--character', 'GARNET',
            '--plasticity-config', config,
            '--out', adapter,
        ], f'materialize-{label}')
        return adapter

    def match(
        name: str,
        adapter: Path,
        opponent: str,
        seed_p1: int,
        seed_p2: int,
        *,
        train: bool = False,
    ) -> dict:
        game_dir = runtime / 'fightingice'
        game_log = out / f'{name}-game.log'
        with game_log.open('wb') as log:
            game = subprocess.Popen([
                'java',
                '-cp', 'FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*',
                'Main',
                '--headless-mode',
                '--pyftg-mode',
                '--input-sync',
                '--limithp', '400', '400',
                '--port', '31415',
                '-r', '1',
                '-f', '3600',
            ], cwd=game_dir, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                for _ in range(90):
                    if game.poll() is not None:
                        raise RuntimeError('game exited before startup')
                    if 'Socket server is started' in game_log.read_text(errors='replace'):
                        break
                    time.sleep(0.5)
                else:
                    raise TimeoutError('game startup timeout')
                command = [
                    bridge,
                    runtime / 'repo/scripts/run_game_malecns_lif.py',
                    '--host', '127.0.0.1',
                    '--port', '31415',
                    '--character-p1', 'GARNET',
                    '--character-p2', opponent,
                    '--seed-p1', str(seed_p1),
                    '--seed-p2', str(seed_p2),
                    '--reference-python', wrapper,
                    '--reference-model', runtime / 'shiu/model.py',
                    '--adapter-dir', base,
                    '--adapter-dir-p1', adapter,
                    '--interface', runtime / 'data/interface.json',
                    '--decision-interval', '60',
                    '--readout-mode-p1', READOUT_MODE,
                    '--readout-mode-p2', 'canonical',
                    '--games', '1',
                    '--expected-rounds', '1',
                    '--timeout', str(max(1, min(600, int(deadline - time.monotonic())))),
                    '--run-id', name,
                    '--out', out / 'matches',
                ]
                if train:
                    command.append('--trainable-trace')
                run(command, name)
            finally:
                stop(game)

        folder = out / 'matches' / name
        status = json.loads((folder / 'status.json').read_text())
        assert status['status'] == MATCH_STATUS
        assert status['readout_modes'] == [READOUT_MODE, 'canonical']
        assert status['readout_contract'] == READOUT_CONTRACT
        assert status['readout_game_state_used'] is False
        assert status['learning_performed'] is False
        assert status['trace_trainable'] is train
        rows = [json.loads(line) for line in (folder / 'p1.jsonl').read_text().splitlines() if line.strip()]
        assert len(rows) == 1
        trace = rows[0]
        assert trace['terminated'] is True and trace['truncated'] is False
        hps = [max(0, value) for value in trace['remaining_hps']]
        initial = trace['transitions'][0]['display']
        return {
            'winner': 'GARNET' if hps[0] > hps[1] else opponent if hps[0] < hps[1] else 'DRAW',
            'p1_hp': hps[0],
            'p2_hp': hps[1],
            'elapsed_frame': trace['elapsed_frame'],
            'elapsed_seconds': trace['elapsed_frame'] / 60,
            'ended_by': 'KO' if min(hps) == 0 else 'TIME_LIMIT',
            'damage_dealt_hp': max(0, initial['p2']['hp'] - hps[1]),
            'damage_taken_hp': max(0, initial['p1']['hp'] - hps[0]),
            'no_damage_draw': hps == [400, 400],
            'decision_count': len(trace['transitions']),
            'requested_action_counts': dict(Counter(str(row['action']) for row in trace['transitions'])),
        }

    parent_adapter = materialize('parent', parent_state, control_cfg)
    training = match(
        'training-reproduction',
        parent_adapter,
        TRAINING_CASE['opponent'],
        TRAINING_CASE['seed_p1'],
        TRAINING_CASE['seed_p2'],
        train=True,
    )
    if not training['no_damage_draw']:
        raise RuntimeError(f'run-2310 training reproduction changed: {training}')

    states = out / 'states'
    control_state = states / 'r2e/GARNET.npz'
    treatment_state = states / 'r2f/GARNET.npz'
    control_state.parent.mkdir(parents=True)
    treatment_state.parent.mkdir(parents=True)
    shutil.copy2(parent_state, control_state)
    shutil.copy2(parent_state.with_suffix('.npz.json'), control_state.with_suffix('.npz.json'))

    fork_code = """import json,sys
from pathlib import Path
from connectome_fighter.combat_checkpoint import config_from_json,fork_reward
source,dest,old_path,new_path=map(Path,sys.argv[1:])
old=config_from_json(json.loads(old_path.read_text()))
new=config_from_json(json.loads(new_path.read_text()))
print(json.dumps(fork_reward(source,dest,old,new),sort_keys=True))
"""
    run([
        bridge, '-c', fork_code,
        parent_state, treatment_state, control_cfg, treatment_cfg,
    ], 'fork-r2f')

    trace_path = out / 'matches/training-reproduction/p1.jsonl'
    spikes_path = out / 'matches/training-reproduction/p1-brain/spikes.parquet'

    def update(label: str, state: Path, reward: Path, config: Path) -> dict:
        summary_path = out / f'update-{label}.json'
        run([
            bridge,
            runtime / 'repo/scripts/update_malecns_valence_plasticity.py',
            '--character', 'GARNET',
            '--side', '1',
            '--round-trace', trace_path,
            '--spikes', spikes_path,
            '--candidates', candidates,
            '--reward-config', reward,
            '--plasticity-config', config,
            '--state', state,
            '--out-summary', summary_path,
        ], f'update-{label}')
        return json.loads(summary_path.read_text())

    control_update = update('r2e', control_state, control_reward, control_cfg)
    treatment_update = update('r2f', treatment_state, treatment_reward, treatment_cfg)

    control_meta = json.loads(control_state.with_suffix('.npz.json').read_text())
    treatment_meta = json.loads(treatment_state.with_suffix('.npz.json').read_text())
    if control_meta['state_sha256'] != CONTROL_PROPOSAL_SHA256 or sha(control_state) != CONTROL_PROPOSAL_SHA256:
        raise RuntimeError('canonical R2e proposal did not reproduce run 2310 byte-for-byte')
    assert control_meta['generation'] == treatment_meta['generation'] == PARENT_GENERATION + 1
    assert treatment_meta['reward_id'] == TREATMENT_REWARD
    assert control_update['reward_id'] == CANONICAL_REWARD
    assert treatment_update['reward_id'] == TREATMENT_REWARD

    control_adapter = materialize('r2e', control_state, control_cfg)
    treatment_adapter = materialize('r2f', treatment_state, treatment_cfg)

    adapters = {
        'parent': parent_adapter,
        'r2e_control': control_adapter,
        'r2f_no_damage_neutral': treatment_adapter,
    }
    evaluations: dict[str, list[dict]] = {label: [] for label in adapters}
    for case in VALIDATION_SUITE:
        for label, adapter in adapters.items():
            metrics = match(
                f"{label}-{case['case_id']}",
                adapter,
                case['opponent'],
                case['seed_p1'],
                case['seed_p2'],
            )
            evaluations[label].append({**case, 'metrics': metrics})

    reward_config = json.loads(control_reward.read_text())

    def gate(after_label: str) -> dict:
        cases = []
        for before, after in zip(evaluations['parent'], evaluations[after_label], strict=True):
            cases.append({
                'case_id': before['case_id'],
                'opponent': before['opponent'],
                'seed_p1': before['seed_p1'],
                'seed_p2': before['seed_p2'],
                'before': before['metrics'],
                'after': after['metrics'],
            })
        return paired_evaluation_suite_gate(cases, reward_config)

    control_gate = gate('r2e_control')
    treatment_gate = gate('r2f_no_damage_neutral')
    if abs(control_gate['utility_delta'] - EXPECTED_CONTROL_GATE_DELTA) > 1e-12:
        raise RuntimeError(f'run-2310 validation replay drifted: {control_gate}')

    if treatment_gate['accepted_update']:
        recommendation = 'advance-r2f-to-new-independent-seed-test'
    elif (
        treatment_gate['utility_delta'] > control_gate['utility_delta'] + 1e-12
        and treatment_gate['outcome_regressions'] <= control_gate['outcome_regressions']
    ):
        recommendation = 'mechanism-improved-relative-to-r2e-but-did-not-beat-parent'
    else:
        recommendation = 'reject-r2f-for-this-counterfactual'

    result = {
        'schema_version': 1,
        'status': 'PASS',
        'kind': 'reward-credit-counterfactual-v1',
        'source_evidence': {
            'workflow_run_id': SOURCE_RUN_ID,
            'workflow_run_number': SOURCE_RUN_NUMBER,
            'parent_generation': PARENT_GENERATION,
            'parent_state_sha256': PARENT_STATE_SHA256,
            'canonical_proposal_state_sha256': CONTROL_PROPOSAL_SHA256,
            'training_case': TRAINING_CASE,
        },
        'training_reproduction': training,
        'reward_treatments': {
            'control': CANONICAL_REWARD,
            'treatment': TREATMENT_REWARD,
            'single_intended_difference': 'terminal.no_damage_draw_penalty: -0.25 -> 0.0',
        },
        'updates': {
            'r2e_control': control_update,
            'r2f_no_damage_neutral': treatment_update,
        },
        'validation_suite': VALIDATION_SUITE,
        'evaluations': evaluations,
        'canonical_gate_replay': control_gate,
        'treatment_gate_replay': treatment_gate,
        'recommendation': recommendation,
        'auto_promotion': False,
        'canonical_learning_changed': False,
        'interpretation_boundary': (
            'This reuses the existing fixed ZEN/LUD/NEZ candidate-selection suite and therefore is a '
            'mechanistic counterfactual, not independent generalization evidence. R2f is a project-defined '
            'FightingICE reward treatment, not an endogenous Drosophila reinforcement pathway. A favorable '
            'result only authorizes a separate test on new seeds; it does not authorize canonical publication.'
        ),
    }
    write(out / 'result.json', result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
