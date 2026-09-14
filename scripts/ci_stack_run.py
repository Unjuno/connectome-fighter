#!/usr/bin/env python3
"""Configure the E2E harness with the workflow's verified per-run artifact.

The dependency descriptor is resolved once, before download. Its asset ID and
byte SHA remain fixed within the run even if the rolling release is replaced.
The E2E harness, source overlay and functional acceptance checks are unchanged.
"""
import json
import os
from pathlib import Path
import re

import ci_stack_e2e


def main():
    if os.environ.get('CI') != 'true' or os.environ.get('VERCEL'):
        raise RuntimeError('standalone CI only')
    path = Path(os.environ['CONNECTOME_CI_RUNTIME_DESCRIPTOR'])
    descriptor = json.loads(path.read_text())
    expected = descriptor['archive_sha256']
    if not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise ValueError('invalid runtime byte SHA')
    if expected != os.environ['RUNTIME_SHA256']:
        raise ValueError('verified download and runtime descriptor differ')
    if type(descriptor['asset_id']) is not int or descriptor['asset_id'] <= 0:
        raise ValueError('invalid selected runtime asset')
    # This configures only dependency identity reporting; it does not replace
    # observations, policies, neural events, physics, media or assertions.
    ci_stack_e2e.EXPECTED_SHA = expected
    return ci_stack_e2e.main()


if __name__ == '__main__':
    raise SystemExit(main())
