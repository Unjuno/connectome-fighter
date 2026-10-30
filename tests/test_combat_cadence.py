"""CPU-only tests for the production 30-minute start-to-start hold."""
from datetime import datetime, timedelta, timezone
import pytest

from scripts.combat_training_cadence import (
    MINIMUM_INTERVAL_SECONDS, parse_utc_timestamp, seconds_to_next_start,
)

START = "2026-10-30T10:00:00Z"


def test_exactly_thirty_minutes_from_authoritative_github_start():
    start = parse_utc_timestamp(START)
    assert MINIMUM_INTERVAL_SECONDS == 1800
    assert seconds_to_next_start(START, start) == 1800
    assert seconds_to_next_start(START, start + timedelta(minutes=12)) == 1080
    assert seconds_to_next_start(START, start + timedelta(minutes=29, seconds=59)) == 1
    assert seconds_to_next_start(START, start + timedelta(minutes=30)) == 0
    assert seconds_to_next_start(START, start + timedelta(hours=5)) == 0


def test_utc_offset_normalized_before_waiting():
    started = "2026-10-30T19:00:00+09:00"
    assert seconds_to_next_start(started, datetime(2026, 10, 30, 10, 20,
                                              tzinfo=timezone.utc)) == 600


@pytest.mark.parametrize("start", ["", "tomorrow", "2026-10-30T10:00:00"])
def test_reject_bad_start_identity(start):
    with pytest.raises(ValueError):
        parse_utc_timestamp(start)


def test_reject_future_and_naive_time():
    with pytest.raises(ValueError, match="future"):
        seconds_to_next_start(START, datetime(2026, 10, 30, 9, 58, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="timezone"):
        seconds_to_next_start(START, datetime(2026, 10, 30, 10, 30))


def test_real_workflow_dispatch_is_self_chained_and_guarded():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    raw = (root/".github/workflows/continuous-training.yml").read_text()
    assert "python scripts/combat_training_cadence.py --started-at" in raw
    assert "gh api --method POST" in raw
    assert "status=in_progress" in raw and "status=queued" in raw
    assert "github.ref == 'refs/heads/main'" in raw
    assert "vars.CONNECTOME_TRAINING_PAUSED != 'true'" in raw
