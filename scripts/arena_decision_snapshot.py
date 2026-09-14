"""Bounded, read-only selection of actually observed decision events.

A slow physical renderer must join by event identity, not by simultaneous
reads of unrelated 'latest' files. No event/frame relabeling or replay occurs.
"""
from collections import OrderedDict
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

from run_live_activity_publisher import compact_brain


class SnapshotError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def event_key(event):
    if not isinstance(event, dict) or not isinstance(event.get('brain'), dict):
        return None
    values = (event.get('round_id'), event.get('frame'), event['brain'].get('trace_decision_index'))
    return values if all(type(v) is int and v >= 0 for v in values) else None


class DecisionHistory:
    MAX_EVENTS_PER_SIDE = 64
    MAX_EVENT_BYTES = 128 * 1024
    MAX_AGE_SECONDS = 30.0

    def __init__(self):
        self.events = {1: OrderedDict(), 2: OrderedDict()}

    def add(self, event):
        key = event_key(event)
        side = event.get('side')
        if key is None or type(side) is not int or side not in (1, 2):
            return
        try:
            encoded = json.dumps(event, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        except (TypeError, ValueError):
            return
        if len(encoded) > self.MAX_EVENT_BYTES:
            return
        records = self.events[side]
        if key in records:
            return  # Repeated events may not refresh an expired source.
        records[key] = (json.loads(encoded), time.monotonic(), hashlib.sha256(encoded).hexdigest())
        while len(records) > self.MAX_EVENTS_PER_SIDE:
            records.popitem(last=False)

    def get(self, side, key, now):
        item = self.events[side].get(key)
        if item is None:
            raise SnapshotError(f'p{side}: requested decision not in observed history')
        event, received_at, digest = item
        age = now - received_at
        if age < 0 or age >= self.MAX_AGE_SECONDS:
            raise SnapshotError(f'p{side}: observed decision expired', 410)
        return event, age, digest


def selected_snapshot(state, request_path):
    try:
        query = parse_qs(urlsplit(request_path).query, max_num_fields=8, strict_parsing=True)
        expected = ('session_id', 'round', 'frame', 'p1', 'p2')
        if any(len(query.get(key, [])) != 1 for key in expected):
            raise ValueError('exactly one value required for every selector')
        values = [query[key][0] for key in ('round', 'frame', 'p1', 'p2')]
        if any(not v.isascii() or not v.isdecimal() or len(v) > 12 for v in values):
            raise ValueError('invalid decision selector')
        round_id, frame, d1, d2 = map(int, values)
    except (ValueError, KeyError) as error:
        raise SnapshotError('invalid snapshot query: ' + str(error), 400) from error
    with state.lock:
        if query['session_id'][0] != state.session_id:
            raise SnapshotError('session identity mismatch')
        if state.process_status != 'running':
            raise SnapshotError('arena is not currently running')
        now = time.monotonic()
        records = {side: state.history.get(side, (round_id, frame, decision), now)
                   for side, decision in ((1, d1), (2, d2))}
        status, error, exit_code = state.process_status, state.error, state.exit_code
    events = {side: item[0] for side, item in records.items()}
    for side, event in events.items():
        if event.get('session_id') != state.session_id or event.get('character') != state.characters[side]:
            raise SnapshotError('stored source session/character mismatch')
        if (event.get('display') or {}).get('frame') != frame:
            raise SnapshotError('source display frame differs; refusing to relabel it')
        if event.get('learning_enabled') is not False or event.get('policy_pixel_access') is not False:
            raise SnapshotError('source policy boundary mismatch')
    if events[1].get('match_id') != events[2].get('match_id'):
        raise SnapshotError('source match mismatch')
    # Reuse the same serializer with immutable selected events. This private
    # object never mutates the live arena or feeds a policy.
    selected = type(state)(session_id=state.session_id, p1=state.characters[1], p2=state.characters[2],
                           max_hp=state.max_hp, rounds_per_session=state.rounds_per_session)
    selected.latest = events
    selected.process_status, selected.error, selected.exit_code = status, error, exit_code
    telemetry = selected.payload()
    telemetry['selection_mode'] = 'observed-decision-history-v1'
    telemetry['latest_at_request'] = False
    return {
        'kind': 'observed-decision-snapshot', 'schema_version': 1,
        'session_id': state.session_id, 'policy_access': False,
        'selection_mode': 'observed-decision-history-v1',
        'telemetry': telemetry,
        'activity': {'schema_version': 1, 'kind': 'male-cns-live-anatomy-activity', 'policy_access': False,
                     'sides': {f'p{side}': compact_brain(event) for side, event in events.items()}},
        'source_events': {f'p{side}': event for side, event in events.items()},
        'source_age_seconds': {f'p{side}': records[side][1] for side in (1, 2)},
        'source_event_sha256': {f'p{side}': records[side][2] for side in (1, 2)},
        'interpretation_boundary': 'Earlier actually observed events selected to match held physical input; not latest-state relabeling, synthetic data, lossless replay, or experimental biological spike recordings.',
    }
