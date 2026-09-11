"""Spectator-only FightingICE screen recorder.

This component is deliberately outside the policy path. It receives official
FightingICE ScreenData through pyftg's StreamInterface and pipes raw 960x640
RGB frames to ffmpeg. No pixels are exposed to the MaleCNS policy.
"""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
from typing import Any

from pyftg.aiinterface.stream_interface import StreamInterface


class FightingICEScreenRecorder(StreamInterface):
    WIDTH = 960
    HEIGHT = 640
    CHANNELS = 3

    def __init__(self, output: str | Path, *, fps: int = 60, ffmpeg: str = "ffmpeg") -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.output = Path(output).resolve()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.fps = int(fps)
        self.ffmpeg = str(ffmpeg)
        self.proc: subprocess.Popen[bytes] | None = None
        self.latest: bytes | None = None
        self.frames = 0
        self.invalid_frames = 0
        self.closed = False
        self.game_initialized = False

    def get_screen_data_flag(self) -> bool:
        return True

    def initialize(self, game_data: Any) -> None:
        if self.proc is not None:
            raise RuntimeError("spectator recorder initialized twice")
        cmd = [
            self.ffmpeg, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-video_size", f"{self.WIDTH}x{self.HEIGHT}",
            "-framerate", str(self.fps), "-i", "pipe:0",
            "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(self.output),
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.game_initialized = True

    def get_screen_data(self, screen_data: Any) -> None:
        raw = bytes(screen_data.display_bytes)
        expected = self.WIDTH * self.HEIGHT * self.CHANNELS
        if len(raw) != expected:
            self.invalid_frames += 1
            self.latest = None
            return
        self.latest = raw

    def processing(self) -> None:
        if self.latest is None:
            return
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("spectator ffmpeg process is not initialized")
        if self.proc.poll() is not None:
            err = b"" if self.proc.stderr is None else self.proc.stderr.read()
            raise RuntimeError(f"spectator ffmpeg exited early: {err.decode('utf-8', 'replace')[-1000:]}")
        self.proc.stdin.write(self.latest)
        self.frames += 1
        self.latest = None

    def game_end(self) -> None:
        self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.proc is None:
            return
        if self.proc.stdin is not None:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.proc.returncode not in (0, None):
            err = b"" if self.proc.stderr is None else self.proc.stderr.read()
            raise RuntimeError(f"spectator ffmpeg failed ({self.proc.returncode}): {err.decode('utf-8', 'replace')[-1000:]}")

    def summary(self) -> dict[str, Any]:
        return {
            "mode": "pyftg-spectator-screen-data",
            "policy_pixel_access": False,
            "width": self.WIDTH,
            "height": self.HEIGHT,
            "fps": self.fps,
            "frames": self.frames,
            "invalid_frames": self.invalid_frames,
            "game_initialized": self.game_initialized,
            "output": str(self.output),
            "output_exists": self.output.is_file(),
            "output_bytes": self.output.stat().st_size if self.output.is_file() else 0,
        }

    def write_summary(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
