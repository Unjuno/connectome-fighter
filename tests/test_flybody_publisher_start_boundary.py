"""Startup/session-boundary contracts for the live FlyBody JSONL tail."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flybody_publisher_start_boundary', ROOT/'scripts/run_live_flybody_publisher.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def decision(index: int, frame: int, *, side: int = 1):
    return {
        'kind':'decision', 'side':side, 'round_id':1, 'frame':frame, 'character':'GARNET',
        'brain': {
            'trace_decision_index':index,
            'output_contributions_top_annotated':[
                {'body_id':101, 'spikes':24, 'superclass':'vnc_motor', 'soma_neuromere':'T1', 'root_side':'L'},
            ],
        },
    }


def append(path: Path, *events):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('ab') as handle:
        for event in events:
            handle.write(json.dumps(event).encode() + b'\n')


def test_live_tail_does_not_treat_preexisting_session_data_as_fresh(tmp_path):
    path = tmp_path/'live-decisions.jsonl'
    append(path, decision(1, 10))
    feed = module.DecisionFeed(path, stale_after_seconds=30, start_at_end=True)
    feed.poll(100.0)
    assert feed.state(1, 100.0)['input_status'] == 'missing'
    assert feed.command(1, 100.0).drive == 0

    append(path, decision(2, 20))
    feed.poll(101.0)
    assert feed.state(1, 101.0)['input_status'] == 'fresh'
    assert feed.state(1, 101.0)['decision']['decision_index'] == 2
    assert feed.command(1, 101.0).drive > 0


def test_rotation_skips_content_already_present_in_replacement_file(tmp_path):
    path = tmp_path/'live-decisions.jsonl'
    path.write_bytes(b'')
    feed = module.DecisionFeed(path, stale_after_seconds=30, start_at_end=True)
    feed.poll(100.0)
    append(path, decision(1, 10))
    feed.poll(101.0)
    assert feed.command(1, 101.0).drive > 0

    replacement = tmp_path/'replacement.jsonl'
    append(replacement, decision(90, 900))
    replacement.replace(path)
    feed.poll(102.0)
    assert feed.state(1, 102.0)['input_status'] == 'missing'
    assert feed.command(1, 102.0).drive == 0

    append(path, decision(91, 910))
    feed.poll(103.0)
    assert feed.state(1, 103.0)['decision']['decision_index'] == 91
    assert feed.command(1, 103.0).drive > 0
