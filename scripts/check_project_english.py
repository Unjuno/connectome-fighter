#!/usr/bin/env python3
"""Require English project-owned text; preserve upstream and binary evidence.

Compatibility *.ja.md paths contain English. Unicode transport tests use escaped
code points so multibyte behavior remains tested without non-English source text.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEXT = {'.md', '.tsx', '.ts', '.js', '.mjs', '.html', '.json', '.py', '.yml', '.yaml'}
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]')

def main() -> int:
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    failures = []
    for name in files:
        path = ROOT / name
        if path.suffix not in TEXT or not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if CJK.search(line):
                failures.append(f'{name}:{number}: non-English project text')
    for name in ('app/layout.tsx', 'site/index.html', 'spectator/index.html'):
        if 'lang="en"' not in (ROOT / name).read_text():
            failures.append(f'{name}: expected English document language')
    if failures:
        print('\n'.join(failures))
        return 1
    print('English project contract: PASS (tracked text and document languages)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
