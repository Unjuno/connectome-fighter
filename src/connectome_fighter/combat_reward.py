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


def paired_evaluation_utility(metrics: dict, config: dict) -> float:
    """Comparable fixed-evaluation utility for candidate acceptance.

    This uses the terminal and net-damage terms from R2e. The proximity-potential
    term is omitted because paired before/after evaluations share the same fixed
    initial condition, making its episode-total contribution a common constant.
    It is an engineering acceptance metric, not a biological reinforcement claim.
    """
    validate_config(config)
    if not isinstance(metrics, dict):
        raise ValueError('evaluation metrics must be an object')
    max_hp = float(config['max_hp'])
    p1 = finite(metrics.get('p1_hp'), 'p1 HP')
    p2 = finite(metrics.get('p2_hp'), 'p2 HP')
    dealt = finite(metrics.get('damage_dealt_hp'), 'damage dealt')
    taken = finite(metrics.get('damage_taken_hp'), 'damage taken')
    if not (0.0 <= p1 <= max_hp and 0.0 <= p2 <= max_hp and 0.0 <= dealt <= max_hp and 0.0 <= taken <= max_hp):
        raise ValueError('evaluation HP/damage outside configured range')
    if abs(dealt - (max_hp - p2)) > 1e-9 or abs(taken - (max_hp - p1)) > 1e-9:
        raise ValueError('evaluation damage does not match final HP')
    elapsed = integer(metrics.get('elapsed_frame'), 'elapsed frame', 1)
    if elapsed > config['round_frame_limit']:
        raise ValueError('evaluation exceeds configured horizon')
    margin = p1 - p2
    total_damage = dealt + taken
    terminal = config['terminal']
    outcome = terminal['win'] if margin > 0 else terminal['loss'] if margin < 0 else terminal['no_damage_draw_penalty'] if total_damage == 0 else terminal['ordinary_draw']
    bonus = terminal['early_ko_win_bonus'] * (1 - elapsed / config['round_frame_limit']) if margin > 0 and p2 == 0 else 0.0
    return float(outcome + config['damage_weight'] * (dealt - taken) / max_hp + bonus)


def paired_evaluation_gate(before: dict, after: dict, config: dict) -> dict:
    """Accept only a strict improvement on the identical frozen evaluation."""
    before_utility = paired_evaluation_utility(before, config)
    after_utility = paired_evaluation_utility(after, config)
    accepted = after_utility > before_utility + 1e-12
    return {
        'accepted_update': accepted,
        'before_utility': before_utility,
        'after_utility': after_utility,
        'utility_delta': after_utility - before_utility,
        'reason': 'strict paired fixed-evaluation improvement' if accepted else 'proposal did not strictly improve paired fixed-evaluation utility',
    }


def paired_evaluation_suite_gate(cases: list[dict], config: dict) -> dict:
    """Gate a candidate on a fixed multi-opponent paired validation suite.

    Each case compares the same opponent and seeds before versus after the
    proposed weight update. Acceptance requires positive mean utility change,
    strict improvement on at least two thirds of cases, and no regression in
    win/draw/loss outcome class. This is a small deterministic validation gate,
    not evidence of population-level generalization.
    """
    validate_config(config)
    if not isinstance(cases, list) or len(cases) < 3:
        raise ValueError('validation suite requires at least three paired cases')
    required_improved = math.ceil(2 * len(cases) / 3)
    seen: set[str] = set()
    rows = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError('validation case must be an object')
        case_id = case.get('case_id')
        opponent = case.get('opponent')
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError('validation case_id must be unique and non-empty')
        if not isinstance(opponent, str) or not opponent:
            raise ValueError('validation opponent missing')
        seen.add(case_id)
        before = case.get('before')
        after = case.get('after')
        before_utility = paired_evaluation_utility(before, config)
        after_utility = paired_evaluation_utility(after, config)
        before_margin = finite(before.get('p1_hp'), 'before p1 HP') - finite(before.get('p2_hp'), 'before p2 HP')
        after_margin = finite(after.get('p1_hp'), 'after p1 HP') - finite(after.get('p2_hp'), 'after p2 HP')
        before_outcome = 1 if before_margin > 0 else -1 if before_margin < 0 else 0
        after_outcome = 1 if after_margin > 0 else -1 if after_margin < 0 else 0
        row = {
            'case_id': case_id,
            'opponent': opponent,
            'before_utility': before_utility,
            'after_utility': after_utility,
            'utility_delta': after_utility - before_utility,
            'before_outcome': before_outcome,
            'after_outcome': after_outcome,
        }
        for key in ('seed_p1', 'seed_p2'):
            if key in case:
                row[key] = integer(case[key], key, 1)
        rows.append(row)
    before_mean = sum(row['before_utility'] for row in rows) / len(rows)
    after_mean = sum(row['after_utility'] for row in rows) / len(rows)
    delta = after_mean - before_mean
    improved = sum(row['utility_delta'] > 1e-12 for row in rows)
    nondegrading = sum(row['utility_delta'] >= -1e-12 for row in rows)
    outcome_regressions = sum(row['after_outcome'] < row['before_outcome'] for row in rows)
    accepted = delta > 1e-12 and improved >= required_improved and outcome_regressions == 0
    if accepted:
        reason = 'multi-opponent validation mean improved, at least two thirds of pairs improved, and no outcome class regressed'
    elif outcome_regressions:
        reason = 'validation rejected because at least one opponent regressed in win/draw/loss outcome class'
    elif improved < required_improved:
        reason = 'validation rejected because fewer than two thirds of paired cases strictly improved'
    else:
        reason = 'validation rejected because mean paired utility did not strictly improve'
    return {
        'accepted_update': accepted,
        'before_utility': before_mean,
        'after_utility': after_mean,
        'utility_delta': delta,
        'improved_pairs': improved,
        'nondegrading_pairs': nondegrading,
        'outcome_regressions': outcome_regressions,
        'required_improved_pairs': required_improved,
        'pair_count': len(rows),
        'cases': rows,
        'reason': reason,
    }


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
