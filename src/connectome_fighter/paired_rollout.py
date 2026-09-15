"""Persistent candidate-only paired-search contract; all scalar scores are unitless.

No remote I/O occurs here. Artifact integrity, effective weights and accepted
updates are different identities. A zero-signal cycle advances the experiment
cursor, not the model generation. This is an engineering optimizer, not a claim
of identified biological plasticity.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from .paired_search import EXPERIMENT, COMBAT_REWARD, CURRICULUM_REWARD

ROLLOUT = 'paired-neural-rollout-v1'
PROTOCOL = {
    'rollout': ROLLOUT, 'experiment': EXPERIMENT,
    'combat_reward': COMBAT_REWARD, 'curriculum_reward': CURRICULUM_REWARD,
    'groups': 8, 'pairs': 4, 'sigma': .04, 'learning_rate': .05,
    'step_norm_cap': .02, 'multiplier_bounds': [.8, 1.0],
    'decision_interval_frames': 60, 'neural_window_ms': 20,
    'round_frame_limit': 3600, 'max_hp': 400,
    'mastery_damage_hp': 40, 'mastery_cycles': 3,
}

def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

PROTOCOL_SHA256 = digest(PROTOCOL)
SUBSTRATE_KEYS = ('anatomy', 'reference', 'interface', 'game', 'worker', 'session', 'contracts', 'observations')

def validate_substrate(value):
    if not isinstance(value, dict) or set(value) != set(SUBSTRATE_KEYS):
        raise ValueError('missing numerical/biological substrate identity')
    for v in value.values(): checked_hash(v)

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    tmp.replace(path)


def integer(value: object, name: str, minimum: int = 0, maximum: int = 1_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'invalid {name}')
    return value


def checked_hash(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch('[a-f0-9]{64}', value) is None:
        raise ValueError('invalid SHA-256 identity')
    return value


def weights_hash(values: np.ndarray) -> str:
    values = np.asarray(values)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError('invalid multiplier array')
    if np.any(values < .8 - 1e-7) or np.any(values > 1):
        raise ValueError('multiplier bounds violated')
    return hashlib.sha256(np.asarray(values, dtype='<f4').tobytes()).hexdigest()


def seeds(cycle: int) -> dict:
    integer(cycle, 'cycle', 1)
    start = 1_000_000 + cycle * 8
    return {'direction': 20_000_000 + cycle, 'training': start,
            'selection': start + 1, 'validation': [start + 2, start + 3],
            'combat': 800101}


@dataclass
class Parent:
    multipliers: np.ndarray
    generation: int
    metadata: dict
    state_path: Path


def load_parent(source: Path, candidate_sha: str, membership: np.ndarray, config: object) -> Parent:
    """Resume new state or explicitly seed once from a verified R2e checkpoint."""
    meta_path = source / 'candidate/search-state.json'
    if not meta_path.exists():
        if (source / 'candidate').exists():
            raise ValueError('incomplete resume checkpoint; refusing seed fallback')
        from .valence_plasticity import load_state
        state_path = source / 'state/GARNET.npz'
        m = json.loads(state_path.with_suffix('.npz.json').read_text())
        if m.get('reward_id') != 'R2e-combat-v1':
            raise ValueError('initial paired rollout requires explicit R2e seed')
        state = load_state(state_path, expected_character='GARNET', n_candidates=len(membership),
                           expected_candidate_sha256=candidate_sha, config=config)
        weights_hash(state.multipliers)
        m = dict(m, rollout=ROLLOUT, cycle_index=0, accepted_update_count=0,
                 origin_generation=state.generation, origin_state_sha256=file_hash(state_path),
                 next_phase='curriculum', mastery_streak=0,
                 weights_sha256=weights_hash(state.multipliers))
        return Parent(state.multipliers.copy(), state.generation, m, state_path)
    m = json.loads(meta_path.read_text())
    required = {'schema_version': 1, 'rollout': ROLLOUT, 'experiment': EXPERIMENT,
                'protocol_sha256': PROTOCOL_SHA256, 'candidate_sha256': candidate_sha,
                'candidate_only': True, 'auto_promotion': False, 'production_compatible': False}
    for key, expected in required.items():
        if m.get(key) != expected or (type(expected) is bool and m.get(key) is not expected):
            raise ValueError('resume contract mismatch: ' + key)
    validate_substrate(m.get('substrate'))
    cycle = integer(m.get('cycle_index'), 'cycle', 1)
    accepted = integer(m.get('accepted_update_count'), 'update count')
    origin = integer(m.get('origin_generation'), 'origin generation')
    integer(m.get('mastery_streak'), 'mastery streak', 0, 3)
    if accepted > cycle or m.get('generation') != origin + accepted or m.get('next_phase') not in ('curriculum', 'combat'):
        raise ValueError('invalid checkpoint counters or phase')
    state_path = source / 'candidate/search-state.npz'
    if file_hash(state_path) != checked_hash(m.get('state_file_sha256')):
        raise ValueError('resume checkpoint bytes do not match metadata')
    with np.load(state_path, allow_pickle=False) as archive:
        values = archive['multipliers'].copy()
        if values.dtype != np.float32 or values.shape != membership.shape or not np.array_equal(archive['membership'], membership):
            raise ValueError('resume membership or shape mismatch')
    if weights_hash(values) != checked_hash(m.get('weights_sha256')):
        raise ValueError('resume effective weights differ from metadata')
    return Parent(values, m['generation'], m, state_path)


def save_checkpoint(dest: Path, parent: Parent, membership: np.ndarray, values: np.ndarray,
                    accepted: bool, candidate_sha: str, validation: list[dict], phase: str) -> dict:
    if type(accepted) is not bool or phase not in ('curriculum', 'combat'):
        raise ValueError('invalid update decision')
    if dest.exists():
        raise ValueError('checkpoint output must be new')
    values = np.asarray(values, dtype=np.float32)
    changed = not np.array_equal(values, parent.multipliers)
    if accepted != changed or values.shape != parent.multipliers.shape:
        raise ValueError('accepted update must match an actual weight change')
    validate_substrate(parent.metadata.get('substrate'))
    current_hash = weights_hash(values)
    cycle = integer(parent.metadata['cycle_index'], 'parent cycle') + 1
    seed_plan = seeds(cycle)
    valid = (phase == 'curriculum' and accepted and len(validation) == 2
             and [v.get('seed') for v in validation] == seed_plan['validation']
             and all(v.get('candidate', {}).get('damage_dealt_hp', -1) >= 40 for v in validation))
    streak = min(3, int(parent.metadata.get('mastery_streak', 0)) + 1) if valid else 0
    next_phase = 'combat' if phase == 'combat' or streak == 3 else 'curriculum'
    dest.mkdir(parents=True)
    state_path = dest / 'search-state.npz'
    np.savez_compressed(state_path, multipliers=values, membership=membership)
    total = int(parent.metadata['accepted_update_count']) + int(accepted)
    origin = int(parent.metadata['origin_generation'])
    m = {'schema_version': 1, 'experiment': EXPERIMENT, 'rollout': ROLLOUT,
         'model': 'bounded-group-perturbation-on-existing-KC-MBON-v1',
         'protocol_sha256': PROTOCOL_SHA256, 'candidate_sha256': checked_hash(candidate_sha),
         'substrate': parent.metadata['substrate'],
         'cycle_index': cycle, 'accepted_update_count': total, 'weights_changed': changed,
         'origin_generation': origin, 'generation': origin + total,
         'origin_state_sha256': parent.metadata['origin_state_sha256'],
         'parent_state_sha256': file_hash(parent.state_path),
         'parent_weights_sha256': weights_hash(parent.multipliers), 'weights_sha256': current_hash,
         'state_file_sha256': file_hash(state_path), 'mastery_streak': streak, 'phase': phase,
         'next_phase': next_phase, 'seed_plan': seed_plan,
         'candidate_only': True, 'auto_promotion': False, 'production_compatible': False}
    write_json(dest / 'search-state.json', m)
    return m


def validate_view(view: dict) -> None:
    if not isinstance(view, dict) or view.get('schema_version') != 1 or view.get('rollout') != ROLLOUT:
        raise ValueError('invalid public rollout envelope')
    if view.get('protocol_sha256') != PROTOCOL_SHA256:
        raise ValueError('public protocol mismatch')
    if view.get('ready') is not True or view.get('status') != 'paired-evaluation-ready':
        raise ValueError('uncompleted public result')
    cycle = integer(view.get('cycle_index'), 'public cycle', 1)
    updates = integer(view.get('accepted_update_count'), 'public updates')
    if updates > cycle:
        raise ValueError('more updates than cycles')
    for key in ('latest', 'previous'):
        row = view.get(key, {})
        if row.get('status') != 'COMPLETED' or row.get('candidate_only') is not True or row.get('auto_promotion') is not False or row.get('policy_pixel_access') is not False:
            raise ValueError('evaluation boundary mismatch')
        if row.get('source_training_run_url') != view.get('source_run_url'):
            raise ValueError('evaluation run mismatch')
        checked_hash(row.get('state_sha256'))
        checked_hash(row.get('video', {}).get('sha256'))
    if view['previous'].get('comparison_phase') != 'before' or view['latest'].get('comparison_phase') != 'after':
        raise ValueError('invalid paired phases')
    if view['previous'].get('evaluation') != view['latest'].get('evaluation'):
        raise ValueError('paired protocol mismatch')


def publication_guard(previous: dict | None, incoming: dict) -> bool:
    """Return False for identical retry; otherwise reject stale/forked publication."""
    validate_view(incoming)
    if previous is not None:
        validate_view(previous)
        if digest(previous) == digest(incoming):
            return False
        if incoming['cycle_index'] != previous['cycle_index'] + 1:
            raise ValueError('stale or skipped parent cycle')
        if incoming.get('parent_view_sha256') != digest(previous):
            raise ValueError('parent publication identity mismatch')
        if incoming['previous']['state_sha256'] != previous['latest']['state_sha256']:
            raise ValueError('parent effective weights mismatch')
        advance = int(incoming['latest']['state_sha256'] != incoming['previous']['state_sha256'])
        if incoming['accepted_update_count'] != previous['accepted_update_count'] + advance:
            raise ValueError('accepted count mismatch')
    elif incoming['cycle_index'] != 1 or incoming.get('parent_view_sha256') is not None:
        raise ValueError('first rollout publication requires cycle one')
    return True
