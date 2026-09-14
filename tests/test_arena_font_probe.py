"""Bash pipefail regression for the actual session font-probe function.

Only fc-list/sudo are stubbed; no game or biological evidence is claimed.
"""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def probe(tmp_path, listing, exit_code=0):
    text = (ROOT / 'deploy/arena-runtime/start-session.sh').read_text()
    function = text.split('ensure_font_runtime() {', 1)[1].split('\n}\n', 1)[0]
    (tmp_path / 'listing').write_text(listing)
    for name, content in {
        'fc-list': f'#!/bin/sh\ncat "{tmp_path}/listing"\nexit {exit_code}\n',
        'sudo': '#!/bin/sh\nexit 97\n',
    }.items():
        path = tmp_path / name
        path.write_text(content)
        path.chmod(0o755)
    return subprocess.run(
        ['bash', '-c', 'set -euo pipefail\nwrite_status(){ :; }\nensure_font_runtime() {' + function + '\n}\nensure_font_runtime'],
        env={**os.environ, 'PATH': str(tmp_path) + ':' + os.environ['PATH']},
        capture_output=True, text=True, timeout=5,
    ).returncode


def test_large_font_listing_does_not_trigger_sigpipe(tmp_path):
    assert probe(tmp_path, 'font: family=Example:style=Regular\n' * 100000) == 0


def test_empty_font_listing_is_not_accepted(tmp_path):
    assert probe(tmp_path, '') != 0


def test_failed_font_command_is_not_accepted(tmp_path):
    assert probe(tmp_path, 'some-font\n', exit_code=7) != 0
