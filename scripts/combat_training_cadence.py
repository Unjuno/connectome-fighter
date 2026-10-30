#!/usr/bin/env python3
"""Bounded start-to-start hold for the authorized combat-training self-dispatch.

The GitHub run's server-side run_started_at timestamp anchors the interval.
No checkpoint, repository, or GitHub API state can be written by this module.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import time

MINIMUM_INTERVAL_SECONDS = 1800


def parse_utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing GitHub workflow start timestamp")
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("malformed workflow start timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("workflow start timestamp requires UTC offset")
    return stamp.astimezone(timezone.utc)


def seconds_to_next_start(started_at: str, now: datetime) -> float:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("current time must have a timezone")
    started = parse_utc_timestamp(started_at)
    elapsed = (now.astimezone(timezone.utc) - started).total_seconds()
    if elapsed < -60:
        raise ValueError("workflow start is unreasonably in the future")
    return max(0.0, MINIMUM_INTERVAL_SECONDS - elapsed)


def wait_until_due(started_at: str) -> None:
    # Never sleep on a large, unverified timestamp or forever. Wall-clock
    # recalculation avoids dispatching early if the job was preempted.
    started = parse_utc_timestamp(started_at)
    while True:
        left = seconds_to_next_start(started.isoformat(), datetime.now(timezone.utc))
        if left <= 0:
            break
        time.sleep(min(left, 60.0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    remaining = seconds_to_next_start(args.started_at, datetime.now(timezone.utc))
    print(f"Requested training cadence: minimum {MINIMUM_INTERVAL_SECONDS} seconds from GitHub workflow start; remaining {remaining:.1f} seconds", flush=True)
    if not args.dry_run:
        wait_until_due(args.started_at)
        print("Start-to-start hold completed; successor may be requested if no sibling run exists.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
