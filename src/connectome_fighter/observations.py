"""Adapter for pyftg-style delayed FrameData, without importing pyftg.

No screen, audio, non-delay frame, is_control callback flag, or opponent
internal policy data is used. Scales are explicit configuration, not SI units.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np
from .contracts import Observation, player_index

@dataclass(frozen=True)
class ObservationScales:
    x_scale: float = 960.0
    y_scale: float = 640.0
    velocity_scale: float = 30.0
    recovery_scale: float = 60.0
    frame_scale: float = 3600.0

    def __post_init__(self) -> None:
        if any(not np.isfinite(x) or x <= 0 for x in vars(self).values()):
            raise ValueError("Every normalization scale must be finite and positive")

def encode_frame(frame: Any, game: Any, player: bool,
                 scales: ObservationScales = ObservationScales()) -> Observation | None:
    idx = player_index(player)
    if frame.empty_flag or frame.current_frame_number <= 0:
        return None
    if len(frame.character_data) != 2:
        raise ValueError("Expected exactly two characters")
    own, opp = frame.character_data[idx], frame.character_data[1 - idx]
    if own is None or opp is None:
        raise ValueError("Missing character in a nonempty frame")
    if len(game.max_hps) != 2 or len(game.max_energies) != 2:
        raise ValueError("Missing game limits")
    if min(game.max_hps) <= 0 or min(game.max_energies) <= 0:
        raise ValueError("Game limits must be positive")
    direction = 1.0 if own.front else -1.0
    values = [
        own.hp / game.max_hps[idx], opp.hp / game.max_hps[1-idx],
        own.energy / game.max_energies[idx], opp.energy / game.max_energies[1-idx],
        direction * (opp.x-own.x) / scales.x_scale,
        (opp.y-own.y) / scales.y_scale,
        direction * own.speed_x / scales.velocity_scale,
        own.speed_y / scales.velocity_scale,
        direction * opp.speed_x / scales.velocity_scale,
        opp.speed_y / scales.velocity_scale,
        own.remaining_frame / scales.recovery_scale,
        opp.remaining_frame / scales.recovery_scale,
        float(own.control), float(opp.control),
        own.y / scales.y_scale, opp.y / scales.y_scale,
        float(own.front == opp.front),
        frame.current_frame_number / scales.frame_scale,
    ]
    raw = np.asarray(values, dtype=np.float32)
    if not np.isfinite(raw).all():
        raise ValueError("Non-finite game observation")
    return Observation(np.clip(raw, -4, 4), int(frame.current_round),
                       int(frame.current_frame_number), bool(own.front))
