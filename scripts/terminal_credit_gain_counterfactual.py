#!/usr/bin/env python3
"""Gen49 terminal-credit calibration on one winning and one losing R2e trace.

The canonical R2e objective and canonical updater are reproduced first. The
experimental treatment keeps R2e unchanged and scales only the terminal
outcome/finish component before KC->MBON modulatory plasticity. Reward selection
uses a separate fixed six-case suite with previously unused seeds. Nothing here
publishes or changes canonical continuous learning.
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

from connectome_fighter.combat_reward import paired_evaluation_utility

REWARD_ID = 'R2e-combat-v1'
READOUT_MODE = 'ema-residual'
READOUT_CONTRACT = 'malecns-temporal-readout-v1'
MATCH_STATUS = 'COMPLETED_WITH_VALIDATED_EXPERIMENTAL_READOUT_TRACES'
PARENT_GENERATION = 49
PARENT_STATE_SHA256 = 'a5c2394d69eecba27c971688dcb88f7992ab872331d8d18d4d9a295d75c4b0fe'
TERMINAL_SIGNAL_GAIN = 0.1

TRAINING_CASES = (
    {
        'case_id': 'win-run-2311',
        'source_run_id': 37194981515,
        'source_run_number': 2311,
        'opponent': 'ZEN',
        'seed_p1': 986465,
        'seed_p2': 949593,
        'expected_winner': 'GARNET',
        'expected_damage_dealt_hp': 35,
        'expected_damage_taken_hp': 20,
        'expected_control_state_sha256': 'e8c60365547c8e264b7c8252cf7c104f96c491168475f6427af620db001dd7e6',
    },
    {
        'case_id': 'loss-run-2312',
        'source_run_id': 37195556700,
        'source_run_number': 2312,
        'opponent': 'LUD',
        'seed_p1': 961650,
        'seed_p2': 875148,
        'expected_winner': 'LUD',
        'expected_damage_dealt_hp': 45,
        'expected_damage_taken_hp': 60,
        'expected_control_state_sha256': '085d10369e4b71fd6f580b5ad3dd93f9764a01bc84a2956e9450e80094926761',
    },
)

REWARD_SELECTION_SUITE = (
    {'case_id': 'zen-terminal-gain-s1', 'opponent': 'ZEN', 'seed_p1': 840111, 'seed_p2': 34011},
    {'case_id': 'zen-terminal-gain-s2', 'opponent': 'ZEN', 'seed_p1': 840112, 'seed_p2': 34012},
    {'case_id': 'lud-terminal-gain-s1', 'opponent': 'LUD', 'seed_p1': 840211, 'seed_p2': 34021},
    {'case_id': 'lud-terminal-gain-s2', 'opponent': 'LUD', 'seed_p1': 840212, 'seed_p2': 34022},
    {'case_id': 'nez-terminal-gain-s1', 'opponent': 'NEZ', 'seed_p1': 840311, 'seed_p2': 34031},
    {'case_id': 'nez-terminal-gain-s2', 'opponent': 'NEZ', 'seed_p1': 840312, 'seed_p2': 34032},
)


def sha(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


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


def terminal_step_fraction(update: dict, starting_mean: float) -> dict:
    previous = float(starting_mean)
    total_step = 0.0
    terminal_step = 0.0
    terminal_events = 0
    rows = update.get('event_metrics') or []
    if not rows:
        raise ValueError('update event metrics missing')
    for event in rows:
        after = float(event['multiplier_mean_after'])
        step = max(0.0, previous - after)
        total_step += step
        terminal_component = float(event.get('terminal_reward', 0.0)) + float(event.get('finish_bonus', 0.0))
        if terminal_component != 0.0:
            terminal_events += 1
            terminal_step += step
        previous = after
    if total_step <= 0.0 or terminal_events != 1:
        raise ValueError('expected one terminal event and positive depression')
    return {
        'total_mean_multiplier_step': total_step,
        'terminal_mean_multiplier_step': terminal_step,
        'nonterminal_mean_multiplier_step': total_step - terminal_step,
        'terminal_step_fraction': terminal_step / total_step,
        'terminal_events': terminal_events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--parent-archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=int, default=3000)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true' or os.environ.get('VERCEL'):
        parser.error('standalone CI only')
    if not 1800 <= args.timeout_seconds <= 3300:
        parser.error('timeout must be 1800..3300 seconds')

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
    assert parent_meta['reward_id'] == REWARD_ID
    assert parent_meta['model'] == 'KC-MBON-valence-depression-v0'
    assert sha(parent_state) == parent_meta['state_sha256'] == PARENT_STATE_SHA256
    parent_mean = float(parent_meta['multiplier_mean'])

    base = runtime / 'data/malecns-shiu-strict-v1'
    candidates = runtime / 'data/malecns-valence-v1/kc_mbon_valence_candidates.parquet'
    plasticity_cfg = ROOT / 'configs/plasticity_combat_v1.json'
    reward_cfg = ROOT / 'configs/reward_r2e_combat_v1.json'
    reward_config = json.loads(reward_cfg.read_text())

    def materialize(label: str, state: Path) -> Path:
        adapter = out / f'adapter-{label}'
        run([
            bridge,
            runtime / 'repo/scripts/materialize_malecns_valence_adapter.py',
            '--base-adapter', base,
            '--candidates', candidates,
            '--state', state,
            '--character', 'GARNET',
            '--plasticity-config', plasticity_cfg,
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

    parent_adapter = materialize('parent', parent_state)
    states = out / 'states'
    training_results = {}
    update_results = {}
    adapters = {'parent': parent_adapter}

    for case in TRAINING_CASES:
        case_id = case['case_id']
        training = match(
            f'training-{case_id}',
            parent_adapter,
            case['opponent'],
            case['seed_p1'],
            case['seed_p2'],
            train=True,
        )
        expected = {
            'winner': case['expected_winner'],
            'damage_dealt_hp': case['expected_damage_dealt_hp'],
            'damage_taken_hp': case['expected_damage_taken_hp'],
            'no_damage_draw': False,
        }
        actual = {key: training[key] for key in expected}
        if actual != expected:
            raise RuntimeError(f'{case_id} training reproduction drifted: {actual} != {expected}')
        training_results[case_id] = training

        control_state = states / case_id / 'control/GARNET.npz'
        treatment_state = states / case_id / 'terminal-gain/GARNET.npz'
        control_state.parent.mkdir(parents=True)
        treatment_state.parent.mkdir(parents=True)
        for state in (control_state, treatment_state):
            shutil.copy2(parent_state, state)
            shutil.copy2(parent_state.with_suffix('.npz.json'), state.with_suffix('.npz.json'))

        trace_path = out / f'matches/training-{case_id}/p1.jsonl'
        spikes_path = out / f'matches/training-{case_id}/p1-brain/spikes.parquet'

        control_summary = out / f'update-{case_id}-control.json'
        run([
            bridge,
            runtime / 'repo/scripts/update_malecns_valence_plasticity.py',
            '--character', 'GARNET',
            '--side', '1',
            '--round-trace', trace_path,
            '--spikes', spikes_path,
            '--candidates', candidates,
            '--reward-config', reward_cfg,
            '--plasticity-config', plasticity_cfg,
            '--state', control_state,
            '--out-summary', control_summary,
        ], f'update-{case_id}-control')
        control_update = json.loads(control_summary.read_text())
        control_meta = json.loads(control_state.with_suffix('.npz.json').read_text())
        if control_meta['state_sha256'] != case['expected_control_state_sha256'] or sha(control_state) != case['expected_control_state_sha256']:
            raise RuntimeError(f'{case_id} canonical proposal hash did not reproduce')

        treatment_summary = out / f'update-{case_id}-terminal-gain.json'
        run([
            bridge,
            runtime / 'repo/scripts/update_malecns_terminal_gain_counterfactual.py',
            '--character', 'GARNET',
            '--side', '1',
            '--round-trace', trace_path,
            '--spikes', spikes_path,
            '--candidates', candidates,
            '--reward-config', reward_cfg,
            '--plasticity-config', plasticity_cfg,
            '--state', treatment_state,
            '--terminal-signal-gain', str(TERMINAL_SIGNAL_GAIN),
            '--out-summary', treatment_summary,
        ], f'update-{case_id}-terminal-gain')
        treatment_update = json.loads(treatment_summary.read_text())
        treatment_meta = json.loads(treatment_state.with_suffix('.npz.json').read_text())
        assert treatment_meta['canonical_training_eligible'] is False
        assert treatment_meta['experimental_terminal_signal_gain'] == TERMINAL_SIGNAL_GAIN

        control_dominance = terminal_step_fraction(control_update, parent_mean)
        treatment_dominance = terminal_step_fraction(treatment_update, parent_mean)
        if control_dominance['terminal_step_fraction'] < 0.85:
            raise RuntimeError(f'{case_id} no longer shows terminal-dominated canonical credit')
        update_results[case_id] = {
            'control': control_update,
            'treatment': treatment_update,
            'control_terminal_dominance': control_dominance,
            'treatment_terminal_dominance': treatment_dominance,
        }
        adapters[f'{case_id}:control'] = materialize(f'{case_id}-control', control_state)
        adapters[f'{case_id}:treatment'] = materialize(f'{case_id}-terminal-gain', treatment_state)

    evaluations: dict[str, list[dict]] = {label: [] for label in adapters}
    for select_case in REWARD_SELECTION_SUITE:
        for label, adapter in adapters.items():
            metrics = match(
                f"selection-{label.replace(':', '-')}-{select_case['case_id']}",
                adapter,
                select_case['opponent'],
                select_case['seed_p1'],
                select_case['seed_p2'],
            )
            evaluations[label].append({**select_case, 'metrics': metrics})

    def outcome(metrics: dict) -> int:
        return 1 if metrics['p1_hp'] > metrics['p2_hp'] else -1 if metrics['p1_hp'] < metrics['p2_hp'] else 0

    def aggregate(rows: list[dict]) -> dict:
        utilities = [paired_evaluation_utility(row['metrics'], reward_config) for row in rows]
        return {
            'cases': len(rows),
            'wins': sum(outcome(row['metrics']) > 0 for row in rows),
            'losses': sum(outcome(row['metrics']) < 0 for row in rows),
            'draws': sum(outcome(row['metrics']) == 0 for row in rows),
            'damage_dealt_hp': sum(row['metrics']['damage_dealt_hp'] for row in rows),
            'damage_taken_hp': sum(row['metrics']['damage_taken_hp'] for row in rows),
            'net_hp': sum(row['metrics']['damage_dealt_hp'] - row['metrics']['damage_taken_hp'] for row in rows),
            'mean_canonical_utility': sum(utilities) / len(utilities),
            'canonical_utilities': utilities,
        }

    def paired_compare(before_label: str, after_label: str) -> dict:
        before_rows = evaluations[before_label]
        after_rows = evaluations[after_label]
        cases = []
        for before, after in zip(before_rows, after_rows, strict=True):
            before_u = paired_evaluation_utility(before['metrics'], reward_config)
            after_u = paired_evaluation_utility(after['metrics'], reward_config)
            before_outcome = outcome(before['metrics'])
            after_outcome = outcome(after['metrics'])
            cases.append({
                'case_id': before['case_id'],
                'opponent': before['opponent'],
                'before_utility': before_u,
                'after_utility': after_u,
                'utility_delta': after_u - before_u,
                'before_outcome': before_outcome,
                'after_outcome': after_outcome,
            })
        return {
            'before': before_label,
            'after': after_label,
            'pair_count': len(cases),
            'mean_utility_delta': sum(row['utility_delta'] for row in cases) / len(cases),
            'improved_pairs': sum(row['utility_delta'] > 1e-12 for row in cases),
            'nondegrading_pairs': sum(row['utility_delta'] >= -1e-12 for row in cases),
            'outcome_regressions': sum(row['after_outcome'] < row['before_outcome'] for row in cases),
            'cases': cases,
        }

    aggregate_results = {label: aggregate(rows) for label, rows in evaluations.items()}
    comparisons = {}
    support = {}
    required_improved = 4
    for case in TRAINING_CASES:
        case_id = case['case_id']
        control_label = f'{case_id}:control'
        treatment_label = f'{case_id}:treatment'
        vs_control = paired_compare(control_label, treatment_label)
        vs_parent = paired_compare('parent', treatment_label)
        comparisons[case_id] = {
            'treatment_vs_control': vs_control,
            'treatment_vs_parent': vs_parent,
            'control_vs_parent': paired_compare('parent', control_label),
        }
        support[case_id] = (
            vs_control['mean_utility_delta'] > 1e-12
            and vs_parent['mean_utility_delta'] > 1e-12
            and vs_control['improved_pairs'] >= required_improved
            and vs_parent['improved_pairs'] >= required_improved
            and vs_control['outcome_regressions'] == 0
            and vs_parent['outcome_regressions'] == 0
        )

    if all(support.values()):
        recommendation = 'advance-terminal-gain-0.1-to-confirmatory-independent-holdout'
    elif any(support.values()):
        recommendation = 'mixed-terminal-gain-effect-do-not-change-canonical-learning'
    else:
        recommendation = 'reject-terminal-gain-0.1-for-these-counterfactuals'

    result = {
        'schema_version': 1,
        'status': 'PASS',
        'kind': 'terminal-credit-gain-counterfactual-v1',
        'parent': {
            'generation': PARENT_GENERATION,
            'state_sha256': PARENT_STATE_SHA256,
        },
        'reward_id': REWARD_ID,
        'canonical_reward_changed': False,
        'terminal_signal_gain': TERMINAL_SIGNAL_GAIN,
        'calibration_rationale': (
            'In source evidence from winning run 2314 and losing run 2312, the terminal +/-2 event accounted '
            'for about 90.8% and 90.6% of the one-match mean multiplier depression. A gain of 0.1 makes the '
            'terminal contribution approximately comparable to the accumulated nonterminal contribution.'
        ),
        'training_cases': TRAINING_CASES,
        'training_reproduction': training_results,
        'updates': update_results,
        'reward_selection_suite': REWARD_SELECTION_SUITE,
        'reward_selection_evaluations': evaluations,
        'reward_selection_aggregate': aggregate_results,
        'reward_selection_pairwise': comparisons,
        'reward_selection_rule': {
            'required_improved_pairs': required_improved,
            'require_positive_mean_vs_control': True,
            'require_positive_mean_vs_parent': True,
            'require_zero_outcome_regressions_vs_control': True,
            'require_zero_outcome_regressions_vs_parent': True,
            'per_training_case_support': support,
        },
        'recommendation': recommendation,
        'auto_promotion': False,
        'canonical_learning_changed': False,
        'interpretation_boundary': (
            'This changes only experiment-time terminal credit gain, not the R2e objective. The six selection '
            'seeds become model-selection data after this run and are not a future independent holdout. Any '
            'favorable result authorizes only a separate confirmatory holdout, not canonical publication. '
            'The reward-to-KC/MBON mapping remains project-defined and is not an identified endogenous '
            'Drosophila reinforcement pathway.'
        ),
    }
    write(out / 'result.json', result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
