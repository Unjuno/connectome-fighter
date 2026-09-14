"""Software contracts with a fake stepper, NOT biological or MuJoCo evidence."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flybody_publisher_under_test', ROOT / 'scripts/run_live_flybody_publisher.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SIMULATOR_CLASS = module.FlyBodySide


class FakeEnv:
    def __init__(self, dt=0.002):
        self.task = SimpleNamespace(control_timestep=dt)
        self.actions = []

    def step(self, action):
        self.actions.append(np.asarray(action).copy())
        return SimpleNamespace(last=lambda: False)


def simulator(drive=True, dt=0.002):
    sim = object.__new__(SIMULATOR_CLASS)
    sim.env = FakeEnv(dt)
    sim.names = ['coxa_T1_left', 'adhere_claw_T1_left']
    sim.minimum = np.array([-1.0, 0.0])
    sim.maximum = np.array([1.0, 1.0])
    sim.command = module.neural_fly_command([
        {'body_id':101, 'spikes':24, 'superclass':'vnc_motor', 'soma_neuromere':'T1', 'root_side':'L'},
    ] if drive else [])
    sim.phase = 0.0
    sim.sim_steps = 0
    sim.resets = 0
    sim.pending_time_seconds = 0.0
    sim.sim_time_seconds = 0.0
    sim.dropped_time_seconds = 0.0
    return sim


def test_capped_stepper_uses_physics_time_not_wall_time():
    sim = simulator()
    sim.advance(0.100)
    assert sim.sim_steps == 16
    expected = (2 * math.pi * 6 * sim.command.drive * (16 * 0.002)) % (2 * math.pi)
    assert sim.phase == pytest.approx(expected, abs=1e-12)


def test_substep_intervals_accumulate_without_overstepping():
    sim = simulator()
    for _ in range(3):
        sim.advance(0.0005)
    assert sim.sim_steps == 0
    sim.advance(0.0005)
    assert sim.sim_steps == 1


def test_zero_elapsed_time_does_not_step():
    sim = simulator()
    sim.advance(0.0)
    assert sim.sim_steps == 0


def test_negative_elapsed_time_is_rejected():
    with pytest.raises(ValueError):
        simulator().advance(-0.1)


def test_zero_drive_is_phase_invariant():
    sim = simulator(drive=False)
    sim.advance(0.1)
    assert sim.phase == 0.0
    assert all(np.array_equal(a, [0.0, 0.0]) for a in sim.env.actions)


@pytest.mark.parametrize('brain', [[], 'malformed', 7])
def test_malformed_brain_fails_closed(brain):
    assert module.compact_command({'brain':brain}).drive == 0


def test_nonfinite_spikes_do_not_poison_json():
    command = module.compact_command({'brain': {'output_contributions_top_annotated': [
        {'body_id':101, 'spikes':float('inf'), 'superclass':'vnc_motor', 'root_side':'L'},
    ]}})
    assert command.drive == 0
    json.dumps(command.to_json(), allow_nan=False)


def test_missing_identity_is_not_fabricated_as_zero():
    assert module.event_identity({'brain':{}}) is None


def decision(side=1, index=1, frame=10, round_id=1):
    return {
        'kind':'decision', 'side':side, 'round_id':round_id, 'frame':frame,
        'character':'GARNET' if side == 1 else 'ZEN',
        'brain': {'trace_decision_index':index, 'output_contributions_top_annotated':[
            {'body_id':101, 'spikes':24, 'superclass':'vnc_motor', 'soma_neuromere':'T1', 'root_side':'L'},
        ]},
    }


def append(path, *events):
    with path.open('ab') as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False).encode() + b'\n')


def test_truncated_log_clears_commands_and_identity(tmp_path):
    path = tmp_path/'decisions.jsonl'
    append(path, decision(1), decision(2))
    feed = module.DecisionFeed(path)
    feed.poll(1.0)
    assert feed.command(1, 1.0).drive > 0
    assert feed.command(2, 1.0).drive > 0
    path.write_bytes(b'')
    feed.poll(2.0)
    for side in (1, 2):
        assert feed.command(side, 2.0).drive == 0
        assert feed.state(side, 2.0)['decision'] is None
        assert feed.state(side, 2.0)['input_status'] == 'missing'
    assert feed.epoch == 1


def test_replaced_larger_log_is_new_epoch(tmp_path):
    path = tmp_path/'decisions.jsonl'
    append(path, decision(1, index=8, frame=80))
    feed = module.DecisionFeed(path)
    feed.poll(1.0)
    replacement = tmp_path/'replacement.jsonl'
    new = decision(2)
    new['extra'] = 'new-file' * 100
    append(replacement, new)
    replacement.replace(path)
    feed.poll(2.0)
    assert feed.command(1, 2.0).drive == 0
    assert feed.command(2, 2.0).drive > 0
    assert feed.epoch == 1


def test_unavailable_source_does_not_keep_motor_command(tmp_path):
    path = tmp_path/'decisions.jsonl'
    append(path, decision())
    feed = module.DecisionFeed(path)
    feed.poll(1.0)
    path.unlink()
    feed.poll(2.0)
    assert feed.command(1, 2.0).drive == 0
    assert feed.state(1, 2.0)['decision'] is None


def test_stale_timeout_is_per_side_and_clears_identity(tmp_path):
    path = tmp_path/'decisions.jsonl'
    append(path, decision(1), decision(2))
    feed = module.DecisionFeed(path, stale_after_seconds=5.0)
    feed.poll(10.0)
    append(path, decision(2, index=2, frame=20))
    feed.poll(13.0)
    assert feed.command(1, 14.999).drive > 0
    assert feed.command(1, 15.0).drive == 0
    assert feed.command(2, 15.0).drive > 0
    assert feed.state(1, 15.0)['input_status'] == 'stale'
    assert feed.state(1, 15.0)['decision'] is None


def test_duplicate_and_regressed_decisions_cannot_refresh_freshness(tmp_path):
    path = tmp_path/'decisions.jsonl'
    append(path, decision(index=3, frame=30))
    feed = module.DecisionFeed(path, stale_after_seconds=5.0)
    feed.poll(10.0)
    append(path, decision(index=3, frame=30), decision(index=2, frame=20), decision(index=4, frame=29))
    feed.poll(14.0)
    assert feed.received_at[1] == 10.0
    assert feed.state(1, 15.0)['input_status'] == 'stale'
    assert feed.rejected_records == 3


def test_new_round_allows_reset_decision_counter(tmp_path):
    path = tmp_path/'decisions.jsonl'
    append(path, decision(index=99, frame=990))
    feed = module.DecisionFeed(path)
    feed.poll(1.0)
    append(path, decision(index=1, frame=10, round_id=2))
    feed.poll(2.0)
    assert feed.state(1, 2.0)['decision'] == {
        'round':2, 'frame':10, 'decision_index':1, 'character':'GARNET',
    }


def test_partial_utf8_record_is_not_consumed_until_newline(tmp_path):
    path = tmp_path/'decisions.jsonl'
    event = decision()
    event['character'] = '\u30c6\u30b9\u30c8'
    payload = json.dumps(event, ensure_ascii=False).encode()
    cut = payload.index('\u30c6'.encode()) + 1
    path.write_bytes(payload[:cut])
    feed = module.DecisionFeed(path)
    feed.poll(1.0)
    assert not feed.latest
    with path.open('ab') as handle:
        handle.write(payload[cut:] + b'\n')
    feed.poll(2.0)
    assert feed.latest[1]['character'] == '\u30c6\u30b9\u30c8'
    assert feed.offset == len(payload) + 1


def test_malformed_records_do_not_prevent_valid_following_record(tmp_path):
    path = tmp_path/'decisions.jsonl'
    path.write_bytes(b'null\n[]\n"string"\n{invalid\n\xff\n')
    malformed = decision()
    malformed['side'] = True
    append(path, malformed, {'kind':'decision', 'side':1, 'brain':[]}, decision())
    feed = module.DecisionFeed(path)
    feed.poll(1.0)
    assert feed.command(1, 1.0).drive > 0
    assert len(feed.latest) == 1
    assert feed.rejected_records == 4


def test_overlong_partial_is_bounded_and_reader_resynchronizes(tmp_path):
    path = tmp_path/'decisions.jsonl'
    path.write_bytes(b'x' * 1025)
    feed = module.DecisionFeed(path)
    feed.MAX_LINE_BYTES = 1024
    feed.poll(1.0)
    assert feed.partial == b''
    assert feed.discarding
    with path.open('ab') as handle:
        handle.write(b'x\n')
    append(path, decision())
    feed.poll(2.0)
    assert feed.command(1, 2.0).drive > 0
    assert not feed.discarding


def test_invalid_neural_row_is_ignored_without_losing_valid_row():
    event = decision()
    event['brain']['output_contributions_top_annotated'] += [
        None, {'body_id':float('inf'), 'spikes':10},
        {'body_id':102, 'spikes':float('nan'), 'superclass':'vnc_motor'},
        {'body_id':103, 'spikes':float('inf'), 'superclass':'vnc_motor'},
        {'body_id':True, 'spikes':10, 'superclass':'vnc_motor'},
    ]
    command = module.compact_command(event)
    assert command.source_body_ids == (101,)
    assert command.source_spikes == 24
    json.dumps(command.to_json(), allow_nan=False)


def test_game_position_action_and_group_labels_do_not_change_motor_command():
    event = decision()
    before = module.compact_command(event)
    event.update(x=800, y=90, action='AIR_A', facing=False)
    event['brain']['output_contributions_top_annotated'][0]['group'] = 'BACKWARD'
    assert module.compact_command(event) == before


@pytest.mark.parametrize('elapsed', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_elapsed_time_is_rejected(elapsed):
    with pytest.raises(ValueError):
        simulator().advance(elapsed)


@pytest.mark.parametrize('dt', [0.0, -0.1, float('nan'), float('inf')])
def test_invalid_physics_timestep_has_no_silent_fallback(dt):
    with pytest.raises(ValueError):
        simulator(dt=dt).advance(0.1)


def test_overload_is_explicit_and_time_balance_is_preserved():
    sim = simulator()
    sim.advance(0.100)
    state = sim.physical_state()
    assert state['sim_time_seconds'] == pytest.approx(0.032)
    assert state['dropped_time_seconds'] == pytest.approx(0.068)
    assert state['pending_time_seconds'] == 0
    assert sum(state[k] for k in ['sim_time_seconds', 'dropped_time_seconds', 'pending_time_seconds']) == pytest.approx(0.100)
    assert state['timebase'] == 'executed-physics-control-steps'
    json.dumps(state, allow_nan=False)


def test_same_physical_step_count_has_same_phase_despite_tick_partition():
    one = simulator()
    many = simulator()
    one.advance(0.020)
    for _ in range(40):
        many.advance(0.0005)
    assert one.sim_steps == many.sim_steps == 10
    assert one.phase == pytest.approx(many.phase, abs=1e-12)
    assert np.array_equal(one.env.actions, many.env.actions)


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf')])
def test_invalid_input_timeout_is_rejected(tmp_path, timeout):
    with pytest.raises(ValueError):
        module.DecisionFeed(tmp_path/'file', stale_after_seconds=timeout)


def test_json_writer_preserves_previous_state_on_nonfinite_payload(tmp_path):
    path = tmp_path/'state.json'
    module.atomic_json(path, {'valid':True})
    before = path.read_bytes()
    with pytest.raises(ValueError):
        module.atomic_json(path, {'invalid':float('inf')})
    assert path.read_bytes() == before


@pytest.mark.parametrize('mode', ['truncate', 'expire'])
def test_main_tails_new_input_then_publishes_zero_after_reset_or_expiry_and_binds_pngs(tmp_path, monkeypatch, mode):
    import hashlib
    import signal

    path = tmp_path/'decisions.jsonl'
    p1, p2, state_path = (tmp_path/name for name in ['p1.png', 'p2.png', 'state.json'])
    # This is intentionally pre-existing data and must not drive a newly started publisher.
    append(path, decision(1), decision(2))
    clock = SimpleNamespace(now=100.0)
    handlers = {}
    snapshots = []

    def fake_side(**kwargs):
        sim = simulator(drive=False)
        sim.render = lambda: np.full((kwargs["height"], kwargs["width"], 3), 10 + len(sim.env.actions), dtype=np.uint8)
        return sim

    def sleep(_delay):
        state = json.loads(state_path.read_text())
        for label, png_path in [('p1', p1), ('p2', p2)]:
            assert state['sides'][label]['png_sha256'] == hashlib.sha256(png_path.read_bytes()).hexdigest()
        snapshots.append(state)
        if len(snapshots) == 1:
            # Only data appended after startup is eligible to become fresh input.
            append(path, decision(1, index=2, frame=20), decision(2, index=2, frame=20))
            clock.now += 0.5
        elif len(snapshots) == 2:
            if mode == 'truncate':
                path.write_bytes(b'')
            clock.now += 0.5
        else:
            handlers[signal.SIGTERM]()

    monkeypatch.setattr(module, 'FlyBodySide', fake_side)
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock.now)
    monkeypatch.setattr(module.time, 'sleep', sleep)
    monkeypatch.setattr(module.signal, 'signal', lambda sig, handler: handlers.__setitem__(sig, handler))
    monkeypatch.setattr(module.sys, 'argv', ['publisher', '--jsonl', str(path), '--p1-output', str(p1),
        '--p2-output', str(p2), '--state-output', str(state_path), '--stale-after-sec', '0.4'])
    assert module.main() == 0
    assert len(snapshots) == 3
    for side in ['p1', 'p2']:
        before = snapshots[0]['sides'][side]
        assert before['neural_command']['drive'] == 0
        assert before['decision'] is None
        assert before['input_status'] == 'missing'
        fresh = snapshots[1]['sides'][side]
        assert fresh['neural_command']['drive'] > 0
        assert fresh['decision']['decision_index'] == 2
        after = snapshots[2]['sides'][side]
        assert after['neural_command']['drive'] == 0
        assert after['decision'] is None
        assert after['input_status'] == ('missing' if mode == 'truncate' else 'stale')
    assert snapshots[2]['publisher'] == 'malecns-flybody-publisher-v2'
    assert snapshots[2]['policy_access'] is False
    assert snapshots[2]['game_telemetry_position_used'] is False
