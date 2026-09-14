"""Engineering fixtures testing selection only, not biological or live-game results."""
import copy
import hashlib
from http.server import ThreadingHTTPServer
import json
import threading
from urllib.request import urlopen

import pytest
from test_live_arena_server import load_module


def event(side, decision=4):
    frame = decision * 60 + 1
    return {'kind': 'decision', 'session_id': 'session', 'match_id': 'match', 'round_id': 1,
            'side': side, 'frame': frame, 'character': 'GARNET' if side == 1 else 'ZEN',
            'learning_enabled': False, 'policy_pixel_access': False, 'action_name': 'B',
            'brain': {'trace_decision_index': decision, 'total_spikes': 12, 'top_spike_bodies': [[123, 12]],
                      'top_spike_bodies_annotated': [{'body_id': 123, 'spikes': 12}]},
            'display': {'frame': frame, 'p1': {'hp': 390, 'x': 100}, 'p2': {'hp': 400, 'x': 800}}}


def setup():
    module = load_module()
    state = module.ArenaState(session_id='session', p1='GARNET', p2='ZEN', max_hp=400)
    state.update(event(1)); state.update(event(2))
    return module, state


def query():
    return '/decision-snapshot?session_id=session&round=1&frame=241&p1=4&p2=4'


def test_select_older_observed_events_without_relabeling_latest():
    module, state = setup()
    state.update(event(1, 5)); state.update(event(2, 5))
    selected = module.selected_snapshot(state, query())
    assert selected['telemetry']['frame'] == 241
    assert selected['activity']['sides']['p1']['frame'] == 241
    assert selected['telemetry']['brain']['p1']['decision_index'] == 4
    assert selected['source_events']['p1'] == event(1)
    assert state.payload()['frame'] == 301
    assert state.latest[1]['brain']['trace_decision_index'] == 5
    assert selected['telemetry']['latest_at_request'] is False
    assert selected['policy_access'] is False
    for side in ('p1', 'p2'):
        digest = hashlib.sha256(json.dumps(selected['source_events'][side], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert digest == selected['source_event_sha256'][side]


@pytest.mark.parametrize('path', [query().replace('p1=4', 'p1=999'), query().replace('session_id=session', 'session_id=other'), query().replace('frame=241', 'frame=240')])
def test_unknown_decision_or_session_is_not_fabricated(path):
    module, state = setup()
    with pytest.raises(module.SnapshotError): module.selected_snapshot(state, path)


@pytest.mark.parametrize('path', [query().replace('&p2=4', ''), query().replace('p2=4', 'p2=-1'), query()+'&p1=4'])
def test_bad_query_is_rejected(path):
    module, state = setup()
    with pytest.raises(module.SnapshotError) as err: module.selected_snapshot(state, path)
    assert err.value.status == 400


def test_ended_game_cannot_be_reported_running_from_history():
    module, state = setup(); state.finish(0)
    with pytest.raises(module.SnapshotError): module.selected_snapshot(state, query())


def test_display_identity_is_not_rewritten_to_force_alignment():
    module, state = setup()
    bad = event(1, 6); bad['display']['frame'] = 99
    state.update(bad); state.update(event(2, 6))
    with pytest.raises(module.SnapshotError): module.selected_snapshot(state, query().replace('241', '361').replace('p1=4', 'p1=6').replace('p2=4', 'p2=6'))


def test_history_is_bounded_and_copied_and_duplicate_does_not_refresh():
    module, state = setup()
    original = event(1, 5); state.update(original)
    stored_time = state.history.events[1][(1, 301, 5)][1]
    original['brain']['total_spikes'] = 999
    state.update(event(1, 5))
    assert state.history.events[1][(1, 301, 5)][0]['brain']['total_spikes'] == 12
    assert state.history.events[1][(1, 301, 5)][1] == stored_time
    with pytest.raises(module.SnapshotError): state.history.get(1, (1, 301, 5), stored_time + 31)
    for n in range(6, 100): state.update(event(1, n))
    assert len(state.history.events[1]) == 64
    assert (1, 301, 5) not in state.history.events[1]


def test_real_http_handler_serves_exact_selection():
    module, state = setup()
    server = ThreadingHTTPServer(('127.0.0.1', 0), module.make_handler(state))
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}' + query(), timeout=3) as response:
            assert response.status == 200
            value = json.load(response)
        assert value['source_events']['p2'] == event(2)
        assert value['telemetry']['frame'] == 241
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=3)
