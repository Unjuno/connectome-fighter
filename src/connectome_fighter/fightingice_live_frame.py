"""Spectator-only latest-frame publisher for official FightingICE ScreenData.

The publisher is deliberately outside the policy path. It receives official
FightingICE RGB ScreenData through pyftg, downsamples it, and atomically writes
one latest PNG for the public spectator. Pixels are never returned to either
MaleCNS policy and never affect action selection or learning.
"""
from __future__ import annotations

import binascii
from pathlib import Path
import struct
import time
from typing import Any
import zlib

import numpy as np
from pyftg.aiinterface.stream_interface import StreamInterface


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def encode_rgb_png(rgb: np.ndarray) -> bytes:
    """Encode uint8 HxWx3 RGB using only stdlib zlib/PNG primitives."""
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("encode_rgb_png expects uint8 HxWx3 RGB")
    height, width, _ = rgb.shape
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    rows = b"".join(b"\x00" + np.ascontiguousarray(rgb[y]).tobytes() for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(rows, 1)) + _png_chunk(b"IEND", b"")


def downsample_rgb(raw: bytes, *, source_width: int = 960, source_height: int = 640, factor: int = 2) -> np.ndarray:
    expected = source_width * source_height * 3
    if len(raw) != expected:
        raise ValueError(f"unexpected ScreenData byte count: {len(raw)} != {expected}")
    if factor <= 0 or source_width % factor or source_height % factor:
        raise ValueError("downsample factor must exactly divide the source dimensions")
    frame = np.frombuffer(raw, dtype=np.uint8).reshape(source_height, source_width, 3)
    return np.ascontiguousarray(frame[::factor, ::factor, :])


class FightingICELiveFramePublisher(StreamInterface):
    SOURCE_WIDTH = 960
    SOURCE_HEIGHT = 640
    CHANNELS = 3

    def __init__(self, output: str | Path, *, fps: float = 10.0, downsample: int = 2) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        if downsample <= 0:
            raise ValueError("downsample must be positive")
        self.output = Path(output).resolve()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.fps = float(fps)
        self.downsample = int(downsample)
        self.latest: bytes | None = None
        self.frames_received = 0
        self.frames_published = 0
        self.invalid_frames = 0
        self.last_publish = 0.0
        self.game_initialized = False

    @property
    def width(self) -> int:
        return self.SOURCE_WIDTH // self.downsample

    @property
    def height(self) -> int:
        return self.SOURCE_HEIGHT // self.downsample

    def get_screen_data_flag(self) -> bool:
        return True

    def initialize(self, game_data: Any) -> None:
        self.game_initialized = True

    def get_screen_data(self, screen_data: Any) -> None:
        raw = bytes(screen_data.display_bytes)
        expected = self.SOURCE_WIDTH * self.SOURCE_HEIGHT * self.CHANNELS
        if len(raw) != expected:
            self.invalid_frames += 1
            return
        self.latest = raw
        self.frames_received += 1

    def processing(self) -> None:
        if self.latest is None:
            return
        now = time.monotonic()
        if now - self.last_publish < 1.0 / self.fps:
            return
        raw = self.latest
        self.latest = None
        image = downsample_rgb(
            raw,
            source_width=self.SOURCE_WIDTH,
            source_height=self.SOURCE_HEIGHT,
            factor=self.downsample,
        )
        png = encode_rgb_png(image)
        tmp = self.output.with_suffix(self.output.suffix + ".tmp")
        tmp.write_bytes(png)
        tmp.replace(self.output)
        self.frames_published += 1
        self.last_publish = now

    def game_end(self) -> None:
        # The shared public process can contain several rounds. Keep the latest
        # valid frame available across a normal round transition.
        return

    def summary(self) -> dict[str, Any]:
        return {
            "mode": "official-fightingice-screendata-latest-png",
            "policy_pixel_access": False,
            "source_width": self.SOURCE_WIDTH,
            "source_height": self.SOURCE_HEIGHT,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "frames_received": self.frames_received,
            "frames_published": self.frames_published,
            "invalid_frames": self.invalid_frames,
            "game_initialized": self.game_initialized,
            "output": str(self.output),
            "output_exists": self.output.is_file(),
            "output_bytes": self.output.stat().st_size if self.output.is_file() else 0,
        }
