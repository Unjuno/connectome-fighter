"""Versioned experimental combat reward; not an endogenous fly signal.

All rewards are dimensionless engineering utility. HP and stage pixels are game
units, not SI physiological quantities. Policy weights stay fixed during play.
"""
from __future__ import annotations

import math
from typing import Any

REWARD_ID = 'R2e-combat-v1'


def finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric data')
    return float(value)


def integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return value


def validate_config(config: dict) -> None:
    if config.get('id') != REWARD_ID or config.get('schema_version') != 2:
        raise ValueError('combat reward version mismatch')
    if config.get('round_frame_limit') != 3600 or config.get('max_hp') != 400:
        raise ValueError('combat reward requires the 3600-frame / 400-HP protocol')
    expected = {'win': 2.0, 'loss': -2.0, 'ordinary_draw': -0.05,
                'no_damage_draw_penalty': -0.25, 'early_ko_win_bonus': 0.25}
    if config.get('terminal') != expected:
        raise ValueError('coefficients changed without a reward version change')
    if config.get('damage_weight') != 1.0:
        raise ValueError('damage coefficient changed')
    if config.get('engagement_potential') != {
        'weight': 0.05, 'contact_band_px': 180.0, 'stage_width_px': 960.0,
        'discount': 1.0, 'terminal_potential': 0.0,
    }:
        raise ValueError('potential shaping version mismatch')


def reward_sequence(round_row: dict, side: int, config: dict, *, require_trainable: bool = True) -> list[dict]:
    """Score a complete round. Offline rescores must explicitly opt out of training.

    Potential is zero at every terminal state. At discount one, its episode sum
    is minus the initial potential, so proximity loops cannot increase total
    shaping return. This does not prove invariance of the KC/MBON update rule.
    """
    validate_config(config)
    if type(side) is not int or side not in (0, 1):
        raise ValueError('invalid player side')
    if round_row.get('kind') != 'round' or round_row.get('terminated') is not True or round_row.get('truncated') is not False:
        raise ValueError('only completed, non-truncated rounds can be scored')
    if require_trainable and round_row.get('trainable') is not True:
        raise ValueError('evaluation or non-trainable traces cannot update state')
    if round_row.get('player_index') != side:
        raise ValueError('trace/player mismatch')
    elapsed = integer(round_row.get('elapsed_frame'), 'elapsed frame', 1)
    horizon = config['round_frame_limit']
    if elapsed > horizon:
        raise ValueError('round exceeds configured horizon')
    max_hp = config['max_hp']

    def hp(value: Any) -> float:
        value = finite(value, 'HP')
        if value > max_hp:
            raise ValueError('HP exceeds configured maximum')
        return max(0.0, value)

    terminal = round_row.get('remaining_hps')
    if not isinstance(terminal, list) or len(terminal) != 2:
        raise ValueError('missing terminal HP')
    final = [hp(v) for v in terminal]
    ko = min(final) == 0.0
    if not ko and elapsed != horizon:
        raise ValueError('early non-KO termination is not a full combat round')
    transitions = round_row.get('transitions')
    if not isinstance(transitions, list) or not transitions:
        raise ValueError('missing decision transitions')
    frames, decisions, health, distances, versions = [], [], [], [], set()
    for row in transitions:
        frames.append(integer(row.get('frame'), 'frame'))
        brain = row.get('brain') or {}
        decisions.append(integer(brain.get('trace_decision_index'), 'decision index'))
        display = row.get('display') or {}
        p1, p2 = display.get('p1') or {}, display.get('p2') or {}
        health.append([hp(p1.get('hp')), hp(p2.get('hp'))])
        distances.append(abs(finite(p1.get('x'), 'p1 x') - finite(p2.get('x'), 'p2 x')))
        version = row.get('policy_version')
        if not isinstance(version, str) or not version:
            raise ValueError('policy provenance missing')
        versions.add(version)
    if len(versions) != 1:
        raise ValueError('policy changed during the round')
    if frames[-1] > elapsed or frames[0] > 1:
        raise ValueError('partial or misaligned decision trace')
    if any(b <= a for a, b in zip(frames, frames[1:])) or any(b <= a for a, b in zip(decisions, decisions[1:])):
        raise ValueError('duplicate or regressed decision identity')
    potential = config['engagement_potential']

    def phi(distance: float) -> float:
        return -min(max(distance - potential['contact_band_px'], 0.0), potential['stage_width_px']) / potential['stage_width_px']

    events = []
    total_damage = 0.0
    for i, initial in enumerate(health):
        last = i == len(health) - 1
        following = final if last else health[i + 1]
        if any(b > a for a, b in zip(initial, following)):
            raise ValueError('HP increased within a no-healing round')
        dealt = initial[1-side] - following[1-side]
        taken = initial[side] - following[side]
        total_damage += dealt + taken
        damage = config['damage_weight'] * (dealt - taken) / max_hp
        next_phi = 0.0 if last else phi(distances[i + 1])
        shaping = potential['weight'] * (next_phi - phi(distances[i]))
        events.append({'decision_index': decisions[i], 'frame': frames[i], 'last': last,
                       'damage_dealt_hp': dealt, 'damage_taken_hp': taken,
                       'damage_reward': damage, 'potential_reward': shaping,
                       'terminal_reward': 0.0, 'finish_bonus': 0.0,
                       'signal': damage + shaping})
    margin = final[side] - final[1-side]
    terminal_cfg = config['terminal']
    outcome = terminal_cfg['win'] if margin > 0 else terminal_cfg['loss'] if margin < 0 else terminal_cfg['no_damage_draw_penalty'] if total_damage == 0 else terminal_cfg['ordinary_draw']
    bonus = terminal_cfg['early_ko_win_bonus'] * (1 - elapsed / horizon) if margin > 0 and final[1-side] == 0 and ko else 0.0
    events[-1]['terminal_reward'] = outcome
    events[-1]['finish_bonus'] = bonus
    events[-1]['signal'] += outcome + bonus
    if not all(math.isfinite(e['signal']) for e in events):
        raise ValueError('non-finite combat reward')
    return events
