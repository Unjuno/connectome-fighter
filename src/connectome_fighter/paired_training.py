"""Persistent paired-search bookkeeping; no game controller or remote writes.

All optimizer coordinates and reward coefficients are dimensionless. Trial count
and accepted weight updates are different counters. No change means no learning.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
from connectome_fighter.paired_search import multipliers, COMBAT_REWARD, CURRICULUM_REWARD

EXPERIMENT = 'paired-neural-training-v1'
CONFIG = {
    'experiment': EXPERIMENT, 'groups': 8, 'pairs_per_cycle': 2,
    'sigma': 0.04, 'learning_rate': 0.05, 'max_step': 0.02,
    'bounds': [0.8, 1.0], 'decision_interval_frames': 60, 'neural_window_ms': 20,
    'round_frame_limit': 3600, 'schedule_minutes': 10,
    'combat': {'id': COMBAT_REWARD, 'win': 1.0, 'draw': 0.0, 'loss': -1.0, 'hp_weight': 0.02},
    'curriculum': {'id': CURRICULUM_REWARD, 'progress': 0.1, 'hit': 0.4, 'damage': 0.5},
    'confirmation_seeds_per_proposal': 2,
}

def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def weights_sha(values) -> str:
    return hashlib.sha256(np.asarray(values, dtype='<f4').tobytes()).hexdigest()

def cycle_seeds(cycle: int) -> dict:
    if type(cycle) is not int or not 1 <= cycle <= 1000000:
        raise ValueError('cycle outside bounded seed namespace')
    # Disjoint blocks, including the two confirmation seeds. These are not
    # held-out tournament seeds; final fixed combat remains a diagnostic.
    base = 2000000 + cycle * 10
    return {'training': base, 'confirmation': [base + 1, base + 2],
            'directions': 20000000 + cycle, 'combat': 800101}

def validate_arrays(origin, theta, membership):
    if np.asarray(theta).shape != (CONFIG['groups'],):
        raise ValueError('wrong search dimension')
    return multipliers(origin, theta, membership)

def load_search(path: Path, meta: dict, candidate_sha: str, membership, runtime_identity: dict):
    if (meta.get('kind') != 'persistent-paired-search-state' or meta.get('experiment') != EXPERIMENT
        or meta.get('schema_version') != 1 or meta.get('config_sha256') != digest(CONFIG)
        or meta.get('candidate_sha256') != candidate_sha or meta.get('runtime_identity') != runtime_identity
        or meta.get('candidate_only') is not True or meta.get('auto_promotion') is not False
        or meta.get('production_compatible') is not False):
        raise ValueError('resume protocol or identity mismatch')
    if meta.get('state_file_sha256') != file_sha(path):
        raise ValueError('resume file checksum mismatch')
    for key in ['cycle', 'accepted_updates', 'total_completed_games']:
        if type(meta.get(key)) is not int or meta[key] < 0:
            raise ValueError('invalid resume counter')
    if meta['accepted_updates'] > meta['cycle']:
        raise ValueError('more updates than cycles')
    with np.load(path, allow_pickle=False) as z:
        if set(z.files) != {'origin', 'theta', 'membership', 'multipliers'}:
            raise ValueError('unexpected state arrays')
        origin, theta = z['origin'].copy(), z['theta'].copy()
        if not np.array_equal(z['membership'], membership):
            raise ValueError('candidate grouping changed')
        expected = validate_arrays(origin, theta, membership)
        if not np.array_equal(expected, z['multipliers']) or weights_sha(expected) != meta.get('weights_sha256'):
            raise ValueError('stored weights do not match search coordinates')
    return origin, theta

def save_search(path: Path, *, origin, theta, membership, parent: dict, runtime_identity: dict,
                candidate_sha: str, completed_games: int, accepted: bool, cycle: int, seed_parent: dict) -> dict:
    values = validate_arrays(origin, theta, membership)
    if cycle != parent.get('cycle', 0) + 1 or type(completed_games) is not int or completed_games < 1:
        raise ValueError('cycle must follow parent and contain completed games')
    changed = weights_sha(values) != parent['weights_sha256']
    if changed != bool(accepted):
        raise ValueError('accepted update must equal actual weight change')
    path.parent.mkdir(parents=True, exist_ok=True)
    # NPZ serialization identity is distinct from the numerical-weight identity.
    with path.open('wb') as f:
        np.savez_compressed(f, origin=np.asarray(origin, dtype=np.float32), theta=np.asarray(theta, dtype=np.float64),
                            membership=np.asarray(membership, dtype=np.int64), multipliers=values)
    meta = {'schema_version': 1, 'kind': 'persistent-paired-search-state', 'experiment': EXPERIMENT,
            'config_sha256': digest(CONFIG), 'runtime_identity': runtime_identity, 'candidate_sha256': candidate_sha,
            'cycle': cycle, 'accepted_updates': parent.get('accepted_updates', 0) + int(accepted),
            'total_completed_games': parent.get('total_completed_games', 0) + completed_games,
            'weights_sha256': weights_sha(values), 'state_file_sha256': file_sha(path),
            'parent_cycle': parent.get('cycle', 0), 'parent_state_file_sha256': parent.get('state_file_sha256'),
            'parent_weights_sha256': parent['weights_sha256'], 'seed_parent': seed_parent,
            'weights_changed': changed, 'candidate_only': True, 'auto_promotion': False, 'production_compatible': False}
    path.with_suffix('.json').write_text(json.dumps(meta, sort_keys=True, indent=2, allow_nan=False)+'\n')
    return meta

def confirmation_pass(rows: list[dict]) -> bool:
    if len(rows) != CONFIG['confirmation_seeds_per_proposal']:
        return False
    gains = []
    for row in rows:
        p, c = row['parent'], row['candidate']
        values = [p[k] for k in ('curriculum_score', 'damage_dealt_hp', 'damage_taken_hp')] + [c[k] for k in ('curriculum_score', 'damage_dealt_hp', 'damage_taken_hp')]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v) for v in values):
            return False
        delta = c['curriculum_score']-p['curriculum_score']
        if delta < -1e-12 or c['damage_dealt_hp'] < p['damage_dealt_hp'] or c['damage_taken_hp'] > p['damage_taken_hp']:
            return False
        gains.append(delta)
    return float(np.mean(gains)) > 1e-12
