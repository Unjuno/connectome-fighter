#!/usr/bin/env python3
"""Experiment-only KC->MBON update with scaled terminal reward credit.

This script is intentionally separate from the canonical updater. It keeps the
R2e reward definition and all KC->MBON plasticity parameters fixed, but scales
only terminal outcome/finish components before they reach the modulatory update.
It never authorizes canonical publication.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from connectome_fighter.combat_reward import REWARD_ID, reward_sequence
from connectome_fighter.valence_plasticity import (
    ValencePlasticityConfig,
    apply_modulatory_signal,
    finish_match,
    load_state,
    save_state,
    sha256_file,
    update_eligibility,
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(row) for row in path.read_text(encoding='utf-8').splitlines() if row.strip()]


def plasticity_config(raw: dict, reward_id: str) -> ValencePlasticityConfig:
    return ValencePlasticityConfig(
        learning_rate=float(raw['learning_rate_per_unit_modulatory_signal']),
        eligibility_decay=float(raw['eligibility_decay_per_decision']),
        pair_count_cap=float(raw['pair_count_cap']),
        normalization_percentile=float(raw['normalization_percentile']),
        multiplier_min=float(raw['multiplier_min']),
        multiplier_max=float(raw['multiplier_max']),
        positive_target=str(raw['positive_signal_target']),
        negative_target=str(raw['negative_signal_target']),
        reward_id=reward_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--character', required=True)
    parser.add_argument('--side', type=int, choices=[1, 2], required=True)
    parser.add_argument('--round-trace', type=Path, required=True)
    parser.add_argument('--spikes', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--reward-config', type=Path, required=True)
    parser.add_argument('--plasticity-config', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--terminal-signal-gain', type=float, required=True)
    parser.add_argument('--round-index', type=int, default=0)
    parser.add_argument('--out-summary', type=Path, required=True)
    args = parser.parse_args()

    gain = float(args.terminal_signal_gain)
    if not np.isfinite(gain) or not (0.0 < gain <= 1.0):
        raise ValueError('terminal signal gain must be finite and in (0,1]')

    reward_cfg = json.loads(args.reward_config.read_text(encoding='utf-8'))
    if reward_cfg.get('id') != REWARD_ID:
        raise ValueError('terminal-gain experiment requires canonical R2e reward')
    raw_plastic = json.loads(args.plasticity_config.read_text(encoding='utf-8'))
    if raw_plastic.get('reward_config') != REWARD_ID:
        raise ValueError('terminal-gain experiment requires canonical R2e plasticity reference')
    cfg = plasticity_config(raw_plastic, REWARD_ID)
    cfg.validate()

    candidates = pd.read_parquet(args.candidates).sort_values('synapse_index').reset_index(drop=True)
    required = {'body_pre', 'body_post', 'mbon_valence_channel', 'sign', 'synapse_index'}
    if not required.issubset(candidates.columns) or candidates.empty:
        raise ValueError('invalid valence candidate table')
    if not (candidates['sign'] == 1).all():
        raise ValueError('candidate sign invariant failed')
    channels = candidates['mbon_valence_channel'].astype(str).to_numpy()
    if set(channels) - {'approach_associated', 'avoidance_associated'}:
        raise ValueError('unresolved candidate channels')
    candidate_sha = sha256_file(args.candidates)

    rounds = read_jsonl(args.round_trace)
    if args.round_index < 0 or args.round_index >= len(rounds):
        raise IndexError('round-index outside trace')
    events = reward_sequence(rounds[args.round_index], args.side - 1, reward_cfg)

    spikes = pd.read_parquet(args.spikes)
    if not {'decision_index', 'body_id'}.issubset(spikes.columns):
        raise ValueError('spike log missing columns')
    counts = spikes.groupby(['decision_index', 'body_id']).size() if not spikes.empty else pd.Series(dtype=np.int64)
    pre = candidates['body_pre'].to_numpy(dtype=np.int64)
    post = candidates['body_post'].to_numpy(dtype=np.int64)

    state = load_state(
        args.state,
        expected_character=args.character,
        n_candidates=len(candidates),
        expected_candidate_sha256=candidate_sha,
        config=cfg,
    )
    before = state.multipliers.copy()
    eligibility = np.zeros(len(candidates), dtype=np.float64)
    event_metrics = []

    for event in events:
        decision = int(event['decision_index'])
        if not spikes.empty and decision in counts.index.get_level_values(0):
            series = counts.loc[decision]
        else:
            series = pd.Series(dtype=np.int64)
        pre_counts = series.reindex(pre, fill_value=0).to_numpy(dtype=np.float64)
        post_counts = series.reindex(post, fill_value=0).to_numpy(dtype=np.float64)
        eligibility = update_eligibility(eligibility, pre_counts, post_counts, cfg)

        local_signal = float(event['damage_reward']) + float(event['potential_reward'])
        terminal_component = float(event['terminal_reward']) + float(event['finish_bonus'])
        scaled_terminal = gain * terminal_component
        scaled_signal = local_signal + scaled_terminal
        metrics = apply_modulatory_signal(state, eligibility, scaled_signal, channels, cfg)
        event_metrics.append({
            **event,
            'original_signal': float(event['signal']),
            'local_signal': local_signal,
            'terminal_component': terminal_component,
            'terminal_signal_gain': gain,
            'scaled_terminal_component': scaled_terminal,
            'scaled_signal': scaled_signal,
            **metrics,
        })

    finish_match(state)
    state_meta = save_state(args.state, state, cfg)
    meta_path = args.state.with_suffix(args.state.suffix + '.json')
    explicit_meta = json.loads(meta_path.read_text(encoding='utf-8'))
    explicit_meta.update({
        'update_kind': 'terminal-credit-gain-counterfactual',
        'experimental_terminal_signal_gain': gain,
        'canonical_training_eligible': False,
    })
    meta_path.write_text(json.dumps(explicit_meta, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    after = state.multipliers.astype(np.float64)
    before64 = before.astype(np.float64)
    absolute_delta = np.abs(after - before64)
    changed = np.flatnonzero(absolute_delta > 1e-12)
    approach = channels == 'approach_associated'
    avoidance = channels == 'avoidance_associated'
    bound_tol = 1e-7
    updates = {
        'changed_edges': int(len(changed)),
        'changed_approach_edges': int(np.count_nonzero(approach[changed])) if len(changed) else 0,
        'changed_avoidance_edges': int(np.count_nonzero(avoidance[changed])) if len(changed) else 0,
        'potentiated_edges': int(np.count_nonzero(after > before64 + 1e-12)),
        'depressed_edges': int(np.count_nonzero(after < before64 - 1e-12)),
        'min_multiplier': float(after.min()),
        'mean_multiplier': float(after.mean()),
        'max_multiplier': float(after.max()),
        'at_lower_bound_edges': int(np.count_nonzero(after <= cfg.multiplier_min + bound_tol)),
        'at_upper_bound_edges': int(np.count_nonzero(after >= cfg.multiplier_max - bound_tol)),
        'mean_abs_multiplier_delta': float(absolute_delta.mean()),
        'max_abs_multiplier_delta': float(absolute_delta.max()),
        'mean_abs_changed_multiplier_delta': float(absolute_delta[changed].mean()) if len(changed) else 0.0,
    }
    updates['at_lower_bound_fraction'] = updates['at_lower_bound_edges'] / len(after)
    updates['at_upper_bound_fraction'] = updates['at_upper_bound_edges'] / len(after)

    summary = {
        'schema_version': 1,
        'status': 'PASS',
        'kind': 'terminal-credit-gain-counterfactual-update',
        'model': 'KC-MBON-valence-depression-v0',
        'reward_id': REWARD_ID,
        'character': args.character,
        'side': args.side,
        'round_index': args.round_index,
        'terminal_signal_gain': gain,
        'signals': {
            'decision_windows': len(events),
            'original_nonzero': sum(float(e['signal']) != 0.0 for e in events),
            'original_sum': float(sum(float(e['signal']) for e in events)),
            'scaled_nonzero': sum(float(e['scaled_signal']) != 0.0 for e in event_metrics),
            'scaled_sum': float(sum(float(e['scaled_signal']) for e in event_metrics)),
            'terminal_component_sum': float(sum(float(e['terminal_component']) for e in event_metrics)),
            'scaled_terminal_component_sum': float(sum(float(e['scaled_terminal_component']) for e in event_metrics)),
        },
        'updates': updates,
        'state': state_meta,
        'event_metrics': event_metrics,
        'invariants': {
            'topology_changed': False,
            'sign_changed': False,
            'potentiation_allowed': False,
            'canonical_training_eligible': False,
            'reward_definition_changed': False,
            'only_terminal_credit_gain_changed': True,
        },
        'interpretation_boundary': (
            'This is an experiment-only change to the mapping from R2e terminal reward components into '
            'KC-MBON modulatory plasticity. It is not a new biological reward pathway and does not modify '
            'canonical continuous learning.'
        ),
    }
    if updates['potentiated_edges'] != 0 or updates['max_multiplier'] > 1.0000001:
        raise RuntimeError('depression-only invariant violated')
    args.out_summary.parent.mkdir(parents=True, exist_ok=True)
    args.out_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': summary['status'],
        'terminal_signal_gain': gain,
        'signals': summary['signals'],
        'updates': updates,
        'state': state_meta,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
