from __future__ import annotations

import struct

import numpy as np
import pytest

from connectome_fighter.rgb_png import downsample_rgb, encode_rgb_png


def test_downsample_and_png_header_dimensions():
    source = np.arange(12 * 8 * 3, dtype=np.uint8).reshape(8, 12, 3)
    sampled = downsample_rgb(source.tobytes(), source_width=12, source_height=8, factor=2)
    assert sampled.shape == (4, 6, 3)
    assert np.array_equal(sampled, source[::2, ::2, :])

    png = encode_rgb_png(sampled)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert png[12:16] == b"IHDR"
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (6, 4)
    assert png.endswith(b"IEND\xaeB`\x82")


def test_downsample_rejects_invalid_byte_count_and_factor():
    with pytest.raises(ValueError, match="byte count"):
        downsample_rgb(b"bad", source_width=4, source_height=4, factor=2)
    with pytest.raises(ValueError, match="exactly divide"):
        downsample_rgb(bytes(5 * 4 * 3), source_width=5, source_height=4, factor=2)
