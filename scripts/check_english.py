#!/usr/bin/env python3
"""Fail when maintained tracked text reintroduces Japanese/CJK UI or prose.

Historical commits and binary evidence are not rewritten. The Unicode transport
regression deliberately retains its characters through escaped Python literals.
"""
from pathlib import Path
import re
import subprocess

pattern = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
failures = []
for name in subprocess.check_output(['git', 'ls-files', '-z'], text=True).split('\0'):
    if not name:
        continue
    p=Path(name)
    try:
        text=p.read_text(encoding='utf-8')
    except (UnicodeError, OSError):
        continue
    for line, content in enumerate(text.splitlines(),1):
        if pattern.search(content):
            failures.append(f'{name}:{line}')
if failures:
    raise SystemExit('Non-English project text: ' + ', '.join(failures))
layout=Path('app/layout.tsx').read_text()
if '<html lang="en">' not in layout:
    raise SystemExit('HTML language must be English')
print('English project text contract: PASS (tracked text, not historical commits/binary evidence)')
