"""Versioned engineering curriculum; independent of candidate acceptance.

Consecutive workflow run numbers rotate ZEN/LUD/NEZ. Skipped or cancelled
workflow numbers can leave gaps; balance of completed games is not guaranteed.
No reward, checkpoint, policy input, or neural parameter is modified here.
"""
from __future__ import annotations

import re

CURRICULUM_ID = 'workflow-attempt-round-robin-v1'
OPPONENTS = ('ZEN', 'LUD', 'NEZ')


def training_curriculum(run_number: str | int) -> dict:
    """Fail closed without an explicit positive GitHub workflow run number.

    A rerun retains the same number and opponent. Rejected candidate updates
    cannot lock the curriculum because generation is deliberately not an input.
    """
    if isinstance(run_number, str):
        if re.fullmatch(r'[1-9][0-9]*', run_number) is None:
            raise ValueError('GITHUB_RUN_NUMBER must be a positive decimal integer')
        number = int(run_number)
    elif type(run_number) is int and run_number > 0:
        number = run_number
    else:
        raise ValueError('GITHUB_RUN_NUMBER must be a positive decimal integer')
    index = (number - 1) % len(OPPONENTS)
    return {
        'protocol': CURRICULUM_ID,
        'workflow_run_number': number,
        'opponent_index': index,
        'opponent': OPPONENTS[index],
        'selection_source': 'GITHUB_RUN_NUMBER',
        'depends_on_accepted_generation': False,
    }
