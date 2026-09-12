"""Project-defined bridge from MaleCNS motor activity to FlyBody controls.

The biological inputs to this module are real MaleCNS body IDs and released
annotations.  The mapping from those spikes to FlyBody actuator trajectories is
an explicit project interface; it is not claimed to be a known native
Drosophila motor-neuron-to-muscle transfer function.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable, Sequence

import numpy as np

MOTOR_SUPERCLASSES = {
    "vnc_motor",
    "cb_motor",
    "vnc_efferent",
    "efferent_descending",
}
DESCENDING_SUPERCLASSES = {"descending_neuron", "efferent_descending"}
LEG_NEUROMERES = ("T1", "T2", "T3")


@dataclass(frozen=True)
class NeuralFlyCommand:
    """Bounded command derived only from annotated neural output activity."""

    drive: float
    left_drive: float
    right_drive: float
    t1_drive: float
    t2_drive: float
    t3_drive: float
    descending_drive: float
    lateral_bias: float
    source_body_ids: tuple[int, ...]
    source_spikes: float

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_body_ids"] = list(self.source_body_ids)
        payload["interpretation_boundary"] = (
            "Real MaleCNS body IDs/annotations feed a project-defined neural-to-FlyBody "
            "motor adapter. The adapter is not a biological muscle innervation map."
        )
        return payload


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _side(row: dict[str, Any]) -> str | None:
    value = (_clean(row.get("root_side")) or _clean(row.get("soma_side"))).upper()
    if value.startswith("L"):
        return "L"
    if value.startswith("R"):
        return "R"
    return None


def _neuromere(row: dict[str, Any]) -> str | None:
    value = _clean(row.get("soma_neuromere")).upper()
    for name in LEG_NEUROMERES:
        if value.startswith(name):
            return name
    return None


def neural_fly_command(
    rows: Iterable[dict[str, Any]],
    *,
    activity_scale_spikes: float = 32.0,
) -> NeuralFlyCommand:
    """Aggregate annotated output-body spikes into a bounded FlyBody command.

    ``rows`` should normally be ``output_contributions_top_annotated`` from the
    canonical MaleCNS worker.  The artificial FightingICE action-group label is
    deliberately ignored: only body annotation and spike contribution are used.
    """
    if activity_scale_spikes <= 0:
        raise ValueError("activity_scale_spikes must be positive")

    eligible: list[tuple[dict[str, Any], float]] = []
    motor_spikes = 0.0
    descending_spikes = 0.0
    left_spikes = 0.0
    right_spikes = 0.0
    segment_spikes = {name: 0.0 for name in LEG_NEUROMERES}

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        try:
            spikes = max(0.0, float(raw.get("spikes", 0.0)))
            body_id = int(raw.get("body_id", 0))
        except (TypeError, ValueError):
            continue
        if body_id <= 0 or spikes <= 0:
            continue
        superclass = _clean(raw.get("superclass")).lower()
        is_motor = superclass in MOTOR_SUPERCLASSES or "motor" in superclass or "efferent" in superclass
        is_descending = superclass in DESCENDING_SUPERCLASSES or "descending" in superclass
        if not (is_motor or is_descending):
            continue

        eligible.append((raw, spikes))
        if is_motor:
            motor_spikes += spikes
        if is_descending:
            descending_spikes += spikes
        side = _side(raw)
        if side == "L":
            left_spikes += spikes
        elif side == "R":
            right_spikes += spikes
        neuromere = _neuromere(raw)
        if neuromere:
            segment_spikes[neuromere] += spikes

    # The scale is a versioned engineering parameter, not a biological constant.
    weighted = motor_spikes + 0.35 * descending_spikes
    drive = float(np.tanh(weighted / activity_scale_spikes))
    descending_drive = float(np.tanh(descending_spikes / activity_scale_spikes))
    lateral_total = left_spikes + right_spikes
    lateral_bias = 0.0 if lateral_total <= 0 else float(np.clip((right_spikes - left_spikes) / lateral_total, -1.0, 1.0))
    left_drive = float(np.tanh(left_spikes / activity_scale_spikes)) if left_spikes > 0 else drive
    right_drive = float(np.tanh(right_spikes / activity_scale_spikes)) if right_spikes > 0 else drive

    def segment(name: str) -> float:
        raw = segment_spikes[name]
        if raw <= 0:
            return 0.35 * drive
        return float(np.tanh(raw / activity_scale_spikes))

    bodies = tuple(sorted({int(row["body_id"]) for row, _ in eligible}))
    return NeuralFlyCommand(
        drive=drive,
        left_drive=left_drive,
        right_drive=right_drive,
        t1_drive=segment("T1"),
        t2_drive=segment("T2"),
        t3_drive=segment("T3"),
        descending_drive=descending_drive,
        lateral_bias=lateral_bias,
        source_body_ids=bodies,
        source_spikes=float(sum(spikes for _, spikes in eligible)),
    )


def _leg_metadata(name: str) -> tuple[str | None, str | None]:
    upper = name.upper()
    segment = next((seg for seg in LEG_NEUROMERES if seg in upper), None)
    side = "L" if "LEFT" in upper else "R" if "RIGHT" in upper else None
    return segment, side


def _joint_phase(name: str) -> float:
    lower = name.lower()
    if "coxa" in lower:
        return 0.0
    if "femur" in lower:
        return math.pi / 2
    if "tibia" in lower:
        return math.pi
    if "tars" in lower or "claw" in lower:
        return -math.pi / 2
    return 0.0


def flybody_action(
    names: Sequence[str],
    minimum: Sequence[float],
    maximum: Sequence[float],
    command: NeuralFlyCommand,
    phase: float,
) -> np.ndarray:
    """Build one FlyBody action vector from a neural command and gait phase.

    The generated action uses FlyBody's real actuator ranges and an explicit
    tripod-like phase convention.  It is intentionally simple and auditable;
    any future learned locomotor controller must be a separate versioned layer.
    """
    lo = np.asarray(minimum, dtype=float)
    hi = np.asarray(maximum, dtype=float)
    if lo.shape != hi.shape or lo.ndim != 1 or len(names) != lo.size:
        raise ValueError("FlyBody action spec dimensions do not match")
    center = (lo + hi) / 2.0
    span = hi - lo
    action = center.copy()
    segment_drive = {"T1": command.t1_drive, "T2": command.t2_drive, "T3": command.t3_drive}

    for idx, name in enumerate(names):
        segment, side = _leg_metadata(name)
        if segment is None or side is None:
            continue
        tripod_a = (segment, side) in {("T1", "L"), ("T2", "R"), ("T3", "L")}
        leg_phase = phase + (0.0 if tripod_a else math.pi)
        side_drive = command.left_drive if side == "L" else command.right_drive
        local_drive = float(np.clip(0.5 * command.drive + 0.3 * segment_drive[segment] + 0.2 * side_drive, 0.0, 1.0))

        if "adhere" in name.lower():
            # Claw adhesion is strongest during the stance half-cycle.
            action[idx] = hi[idx] if math.sin(leg_phase) < 0 else lo[idx]
            continue

        amplitude = 0.16 * span[idx] * local_drive
        target = center[idx] + amplitude * math.sin(leg_phase + _joint_phase(name))
        action[idx] = float(np.clip(target, lo[idx], hi[idx]))

    return action
