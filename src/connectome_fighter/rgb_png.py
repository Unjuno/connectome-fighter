"""Small dependency-light RGB downsample and PNG helpers for spectator output."""
from __future__ import annotations

import binascii
import struct
import zlib

import numpy as np


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def encode_rgb_png(rgb: np.ndarray) -> bytes:
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
