#!/usr/bin/env python3
"""Append the latest candidate-training status to the public research ledger.

This script records research-candidate progression only. It must never promote a
candidate, mutate Vercel state, or reinterpret candidate training as production
performance evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def validate_status(status: dict[str, Any]) -> None:
    if status.get("kind") != "canonical-continuous-training-candidate":
        raise ValueError("unexpected training status kind")
    if status.get("status") != "candidate-only-not-arena-approved":
        raise ValueError("training status is not candidate-only")
    if status.get("served_by_vercel") is not False:
        raise ValueError("candidate status must not be served by Vercel")
    if status.get("auto_promotion") is not False:
        raise ValueError("candidate status must not auto-promote")
    if status.get("character") != "GARNET":
        raise ValueError("current single-writer lane must remain GARNET")
    generation = int(status.get("generation", -1))
    matches = int(status.get("matches", -1))
    if generation < 2 or matches < 2:
        raise ValueError("candidate generation/match counters are invalid")
    sha = str(status.get("state_sha256", ""))
    if not SHA256_RE.fullmatch(sha):
        raise ValueError("candidate state_sha256 is invalid")
    source = str(status.get("source_run_url", ""))
    if not source.startswith("https://github.com/Unjuno/connectome-fighter/actions/runs/"):
        raise ValueError("candidate source_run_url is outside the canonical Actions ledger")


def compact_entry(status: dict[str, Any]) -> dict[str, Any]:
    # Preserve the scientific fields that let a reader reconstruct candidate
    # progression without embedding large trace artifacts in GitHub Pages.
    return {
        "updated_at": status.get("updated_at"),
        "character": status.get("character"),
        "generation": int(status["generation"]),
        "matches": int(status["matches"]),
        "opponent": status.get("opponent"),
        "state_sha256": status.get("state_sha256"),
        "source_kind": status.get("source_kind"),
        "source_run_url": status.get("source_run_url"),
        "match_status": status.get("match_status"),
        "model": status.get("model"),
        "reward_id": status.get("reward_id"),
        "signal_summary": status.get("signal_summary") or {},
        "update_summary": status.get("update_summary") or {},
        "status": status.get("status"),
        "served_by_vercel": False,
        "auto_promotion": False,
        "interpretation_boundary": status.get("interpretation_boundary"),
    }


def append_history(status_path: Path, history_path: Path) -> dict[str, Any]:
    status = read_json(status_path)
    if not isinstance(status, dict):
        raise ValueError("training status must be a JSON object")
    validate_status(status)
    entry = compact_entry(status)

    raw = read_json(
        history_path,
        {"schema_version": 1, "kind": "canonical-continuous-training-history", "entries": []},
    )
    if not isinstance(raw, dict) or raw.get("kind") != "canonical-continuous-training-history":
        raise ValueError("unexpected training history kind")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ValueError("training history entries must be a list")

    generation = entry["generation"]
    sha = entry["state_sha256"]
    same_generation = [row for row in entries if int(row.get("generation", -1)) == generation]
    for row in same_generation:
        if row.get("state_sha256") == sha:
            # workflow_run can be retried; exact duplicates are idempotent.
            return raw
        raise ValueError(f"generation {generation} already exists with a different state SHA")

    if entries:
        latest_generation = max(int(row.get("generation", -1)) for row in entries)
        latest_matches = max(int(row.get("matches", -1)) for row in entries)
        if generation <= latest_generation:
            raise ValueError("candidate generation did not advance monotonically")
        if int(entry["matches"]) <= latest_matches:
            raise ValueError("candidate match counter did not advance monotonically")

    entries.append(entry)
    entries.sort(key=lambda row: (int(row.get("generation", -1)), str(row.get("updated_at", ""))))
    out = {
        "schema_version": 1,
        "kind": "canonical-continuous-training-history",
        "entry_count": len(entries),
        "latest_generation": max(int(row.get("generation", -1)) for row in entries),
        "latest_state_sha256": entries[-1].get("state_sha256"),
        "entries": entries,
        "interpretation_boundary": (
            "This ledger records GitHub research-candidate updates only. Entries are not arena approval, "
            "not proof of improved fighting performance, and are never served by Vercel without a separate promotion gate."
        ),
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    args = parser.parse_args()
    out = append_history(args.status, args.history)
    print(json.dumps({
        "status": "PASS",
        "entry_count": out["entry_count"],
        "latest_generation": out["latest_generation"],
        "latest_state_sha256": out["latest_state_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
