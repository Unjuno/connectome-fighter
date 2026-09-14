"""Explicit reward-version fork; weights and old source files remain unchanged."""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
from connectome_fighter.valence_plasticity import ValencePlasticityConfig, load_state, save_state, sha256_file
from connectome_fighter.combat_reward import REWARD_ID


def config_from_json(raw: dict) -> ValencePlasticityConfig:
    return ValencePlasticityConfig(
        learning_rate=float(raw['learning_rate_per_unit_modulatory_signal']),
        eligibility_decay=float(raw['eligibility_decay_per_decision']),
        pair_count_cap=float(raw['pair_count_cap']),
        normalization_percentile=float(raw['normalization_percentile']),
        multiplier_min=float(raw['multiplier_min']), multiplier_max=float(raw['multiplier_max']),
        positive_target=raw['positive_signal_target'], negative_target=raw['negative_signal_target'],
        reward_id=raw['reward_config'])


def fork_reward(source: Path, destination: Path, old: ValencePlasticityConfig, new: ValencePlasticityConfig) -> dict:
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError('fork destination must be new and separate')
    if old.reward_id != 'R2d-v0' or new.reward_id != REWARD_ID or replace(new, reward_id=old.reward_id) != old:
        raise ValueError('reward fork must preserve all plasticity parameters')
    meta = json.loads(source.with_suffix(source.suffix + '.json').read_text())
    source_hash, meta_hash = sha256_file(source), sha256_file(source.with_suffix(source.suffix + '.json'))
    state = load_state(source, expected_character='GARNET', n_candidates=int(meta['n_candidates']),
                       expected_candidate_sha256=meta['candidate_sha256'], config=old)
    original = state.multipliers.copy()
    state.config_sha256 = new.fingerprint()
    result = save_state(destination, state, new)
    restored = load_state(destination, expected_character='GARNET', n_candidates=len(original),
                          expected_candidate_sha256=state.candidate_sha256, config=new)
    if not np.array_equal(original, restored.multipliers) or sha256_file(source) != source_hash:
        raise RuntimeError('reward fork altered inherited weights or source')
    receipt = {'kind':'explicit-reward-version-fork', 'from_reward':old.reward_id, 'to_reward':new.reward_id,
               'parent_state_sha256':source_hash, 'parent_metadata_sha256':meta_hash,
               'parent_generation':meta['generation'], 'parent_config_sha256':old.fingerprint(),
               'new_config_sha256':new.fingerprint(), 'weights_identical':True, 'state':result}
    destination.with_suffix('.fork.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt
