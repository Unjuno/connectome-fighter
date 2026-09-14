"""Separate, bounded paired-search experiment. No production mutations.

Scores are dimensionless. HP, frame numbers and coordinates are game units,
not biological/SI measurements. Curriculum outcomes are NOT combat strength.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Any

import numpy as np

EXPERIMENT = 'paired-neural-search-v1'
COMBAT_REWARD = 'outcome-hp-epsilon002-v1'
CURRICULUM_REWARD = 'approach-hit-damage-v1'


def finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def score_round(row: dict, samples: list[dict], *, side: int = 0) -> dict:
    """Score a complete 400-HP/3600-frame no-healing game, never a truncation.

    Minimum distance is over recorded delayed FrameData, not unobserved frames.
    Samples supplement only the spectator scorer, never the acting policy.
    """
    if type(side) is not int or side not in (0, 1):
        raise ValueError('invalid side')
    if row.get('kind') != 'round' or row.get('terminated') is not True or row.get('truncated') is not False:
        raise ValueError('complete non-truncated round required')
    if row.get('player_index') != side:
        raise ValueError('player mismatch')
    elapsed = row.get('elapsed_frame')
    if type(elapsed) is not int or not 1 <= elapsed <= 3600:
        raise ValueError('invalid full-round horizon')
    raw_final = row.get('remaining_hps')
    if not isinstance(raw_final, list) or len(raw_final) != 2:
        raise ValueError('terminal HP missing')

    def health(v):
        v = finite(v, 'HP')
        if v > 400:
            raise ValueError('HP exceeds protocol')
        return max(0.0, v)

    final = [health(v) for v in raw_final]
    if min(final) > 0 and elapsed != 3600:
        raise ValueError('early non-KO termination')
    transitions = row.get('transitions')
    if not isinstance(transitions, list) or not transitions or not samples:
        raise ValueError('missing recorded decisions or frames')
    versions = {t.get('policy_version') for t in transitions}
    if len(versions) != 1 or not all(isinstance(v, str) and v for v in versions):
        raise ValueError('policy must remain frozen')
    frames = [t.get('frame') for t in transitions]
    decisions = [(t.get('brain') or {}).get('trace_decision_index') for t in transitions]
    for sequence in (frames, decisions):
        if any(type(v) is not int or v < 0 for v in sequence) or any(b <= a for a, b in zip(sequence, sequence[1:])):
            raise ValueError('invalid or regressed identity')
    if frames[0] != 1 or frames[-1] > elapsed:
        raise ValueError('partial decision trace')
    sf = [s.get('frame') for s in samples]
    if any(type(v) is not int or v < 1 for v in sf) or sf[0] != 1 or sf[-1] > elapsed or any(b <= a for a, b in zip(sf, sf[1:])):
        raise ValueError('invalid sampled frame order')
    hp_rows = [[health(s[p]['hp']) for p in ('p1', 'p2')] for s in samples]
    if hp_rows[0] != [400.0, 400.0]:
        raise ValueError('400/400 start required')
    if [health(transitions[0]['display'][p]['hp']) for p in ('p1','p2')] != hp_rows[0]:
        raise ValueError('decision/sample start mismatch')
    for a, b in zip(hp_rows, hp_rows[1:] + [final]):
        if any(y > x for x, y in zip(a, b)):
            raise ValueError('HP increase in no-healing round')
    distances = [abs(finite(s['p1']['x'], 'x') - finite(s['p2']['x'], 'x')) for s in samples]
    initial_distance, minimum_distance = distances[0], min(distances)
    progress = max(0.0, 1.0 - minimum_distance / initial_distance) if initial_distance > 0 else 0.0
    dealt, taken = 400.0 - final[1-side], 400.0 - final[side]
    outcome = float(np.sign(final[side] - final[1-side]))
    hp_margin = (final[side] - final[1-side]) / 400.0
    action_counts = dict(Counter(str(t['action']) for t in transitions))
    signature_rows = [{'frame':t['frame'], 'action':t['action'],
                       'groups':(t.get('brain') or {}).get('group_spike_counts', {})} for t in transitions]
    import json
    signature = hashlib.sha256(json.dumps(signature_rows, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    first_hit = next((s['frame'] for s, hs in zip(samples, hp_rows) if hs[1-side] < 400), None)
    return {'combat_reward_id':COMBAT_REWARD, 'curriculum_reward_id':CURRICULUM_REWARD,
            'combat_score':outcome + .02 * hp_margin,
            'curriculum_score':.1 * progress + .4 * float(dealt > 0) + .5 * dealt / 400.0,
            'outcome':outcome, 'p1_hp':final[0], 'p2_hp':final[1],
            'damage_dealt_hp':dealt, 'damage_taken_hp':taken,
            'initial_distance_px':initial_distance, 'minimum_observed_distance_px':minimum_distance,
            'approach_progress':progress, 'first_observed_hit_frame':first_hit,
            'no_damage_draw':final == [400.0,400.0], 'elapsed_frame':elapsed,
            'decision_count':len(transitions), 'requested_action_counts':action_counts,
            'observed_frame_count':len(samples), 'observed_frame_gap_count':sum(b-a-1 for a,b in zip(sf,sf[1:])),
            'decision_activity_sha256':signature}


def group_indices(indices: np.ndarray, groups: int = 8) -> np.ndarray:
    indices = np.asarray(indices)
    if type(groups) is not int or not 1 <= groups <= 64 or indices.ndim != 1 or indices.dtype.kind not in 'iu':
        raise ValueError('invalid grouping')
    if len(set(indices.tolist())) != len(indices) or np.any(indices < 0):
        raise ValueError('unique nonnegative synapse IDs required')
    return np.array([int.from_bytes(hashlib.sha256(f'{EXPERIMENT}:{int(v)}'.encode()).digest()[:8], 'big') % groups
                     for v in indices], dtype=np.int64)


def multipliers(parent: np.ndarray, theta: np.ndarray, membership: np.ndarray) -> np.ndarray:
    parent, theta, membership = np.asarray(parent), np.asarray(theta), np.asarray(membership)
    if parent.ndim != 1 or not len(parent) or theta.ndim != 1 or not len(theta) or membership.shape != parent.shape:
        raise ValueError('parameter shape mismatch')
    if membership.dtype.kind not in 'iu' or np.any(membership < 0) or np.any(membership >= len(theta)):
        raise ValueError('invalid membership')
    if not np.isfinite(parent).all() or not np.isfinite(theta).all() or np.any(parent < .8-1e-7) or np.any(parent > 1):
        raise ValueError('invalid bounded parameters')
    # Clipping belongs to the evaluated objective. The estimator is for that
    # objective's Gaussian smoothing, not an unclipped biological derivative.
    return np.clip(parent.astype(np.float64) + theta[membership], .8, 1.0).astype(np.float32)


def propose(directions, plus, minus, *, sigma=.04, learning_rate=.05, max_step=.02):
    u, p, m = np.asarray(directions, dtype=float), np.asarray(plus, dtype=float), np.asarray(minus, dtype=float)
    if u.ndim != 2 or min(u.shape) < 1 or p.shape != (len(u),) or m.shape != p.shape:
        raise ValueError('invalid paired sample shapes')
    if any(not math.isfinite(v) or v <= 0 for v in (sigma,learning_rate,max_step)) or not all(np.isfinite(v).all() for v in (u,p,m)):
        raise ValueError('nonfinite samples or invalid search scale')
    difference = p-m
    gradient = np.mean(difference[:,None]*u, axis=0)/(2*sigma)
    step = learning_rate*gradient
    norm = float(np.linalg.norm(step))
    if norm > max_step:
        step *= max_step/norm
    return gradient, step
