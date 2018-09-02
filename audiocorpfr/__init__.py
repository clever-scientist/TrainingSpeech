import json
import os
from datetime import timedelta

from audiocorpfr import utils

CURRENT_DIR = os.path.dirname(__file__)


def source_info(name: str) -> dict:
    alignment_file = os.path.join(CURRENT_DIR, f'../data/alignments/{name}.json')
    if not os.path.exists(alignment_file):
        return dict(
            status='PENDING',
            progress=0.,
            approved_duration=timedelta(seconds=0.),
            approved_count=0,
        )
    with open(alignment_file) as f:
        fragments = json.load(f)
    todo_dur = sum(f['end'] - f['begin'] for f in fragments)
    approved = [f for f in fragments if f.get('approved')]
    approved_dur = sum(f['end'] - f['begin'] for f in approved)
    disabled_dur = sum(f['end'] - f['begin'] for f in fragments if f.get('disabled'))

    remaining_dur = round(todo_dur - approved_dur - disabled_dur, 3)
    if remaining_dur > 0:
        return dict(
            status='WIP',
            progress=(approved_dur + disabled_dur) / todo_dur,
            approved_duration=timedelta(seconds=approved_dur),
            approved_count=len(approved),
        )

    return dict(
        status='DONE',
        progress=1.,
        approved_duration=timedelta(seconds=approved_dur),
        approved_count=len(approved),
    )



