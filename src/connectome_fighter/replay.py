"""Convert audited fight traces into compact browser-viewable replay telemetry."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .contracts import Action


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def completed_rounds(path: str | Path) -> list[dict[str, Any]]:
    return [x for x in read_jsonl(path) if x.get("kind") == "round" and x.get("terminated")]


def _by_frame(round_payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(t["frame"]): t for t in round_payload.get("transitions", [])}


def _activity(t: dict[str, Any] | None) -> dict[str, Any] | None:
    if not t:
        return None
    brain = t.get("brain") or {}
    activation = brain.get("activation")
    if not isinstance(activation, dict):
        return None
    # readout_features are intentionally excluded from public replay telemetry.
    return {
        "mean": activation.get("mean"),
        "max": activation.get("max"),
        "fraction_gt_0_75": activation.get("fraction_gt_0_75"),
        "top_global": activation.get("top_global", []),
        "top_change": activation.get("top_change", []),
        "top_descending": activation.get("top_descending", []),
    }


def export_replay(
    p1_trace: str | Path,
    p2_trace: str | Path,
    out: str | Path,
    *,
    p1_character: str,
    p2_character: str,
) -> dict[str, Any]:
    r1s, r2s = completed_rounds(p1_trace), completed_rounds(p2_trace)
    if not r1s or not r2s:
        raise ValueError("Replay requires one completed round from both players")
    r1, r2 = r1s[-1], r2s[-1]
    if r1.get("match_id") != r2.get("match_id") or r1.get("round_id") != r2.get("round_id"):
        raise ValueError("Trace pair does not describe the same round")
    m1, m2 = _by_frame(r1), _by_frame(r2)
    frames = sorted(set(m1) | set(m2))
    if not frames:
        raise ValueError("Replay has no decisions")
    rendered: list[dict[str, Any]] = []
    last1: dict[str, Any] | None = None
    last2: dict[str, Any] | None = None
    last_display: dict[str, Any] | None = None
    for frame in frames:
        if frame in m1:
            last1 = m1[frame]
        if frame in m2:
            last2 = m2[frame]
        display = (m1.get(frame) or {}).get("display") or (m2.get(frame) or {}).get("display")
        if display:
            last_display = display
        if last_display is None:
            continue
        p1d, p2d = last_display.get("p1", {}), last_display.get("p2", {})
        rendered.append({
            "frame": int(frame),
            "p1": {
                "hp": p1d.get("hp"), "energy": p1d.get("energy"),
                "x": p1d.get("x"), "y": p1d.get("y"),
                "action": Action(int(last1["action"])).name if last1 else "NEUTRAL",
                "activity": _activity(last1),
            },
            "p2": {
                "hp": p2d.get("hp"), "energy": p2d.get("energy"),
                "x": p2d.get("x"), "y": p2d.get("y"),
                "action": Action(int(last2["action"])).name if last2 else "NEUTRAL",
                "activity": _activity(last2),
            },
        })
    reward = float(r1.get("outcome_reward", 0.0))
    winner = p1_character if reward > 0 else p2_character if reward < 0 else "DRAW"
    replay = {
        "schema_version": 1,
        "match_id": r1["match_id"],
        "round_id": r1["round_id"],
        "p1": {
            "character": p1_character,
            "label": p1_character,
            "checkpoint": (r1.get("transitions") or [{}])[0].get("policy_version"),
        },
        "p2": {
            "character": p2_character,
            "label": p2_character,
            "checkpoint": (r2.get("transitions") or [{}])[0].get("policy_version"),
        },
        "result": {"winner": winner, "p1_reward": reward, "remaining_hps": r1.get("remaining_hps")},
        "frames": rendered,
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(replay, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return replay
