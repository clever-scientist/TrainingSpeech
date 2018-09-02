import json
import os
from datetime import timedelta
from marshmallow import Schema, fields, ValidationError

from audiocorp import utils

CURRENT_DIR = os.path.dirname(__file__)


class LocalFileField(fields.Str):
    def _deserialize(self, value, attr, data):
        value = super()._deserialize(value, attr, data)
        if self.metadata.get('extension') and utils.file_extension(value) != self.metadata['extension']:
            raise ValidationError(f'expect extension to be {self.metadata["extension"]}')
        if self.metadata.get('dirname'):
            value = os.path.join(self.metadata['dirname'], value)
        if not os.path.isfile(value):
            raise ValidationError(f'file not found')
        return os.path.abspath(value)


class SourceSchema(Schema):
    audio_licence = fields.String(required=True)
    audio_page = fields.Url(required=True)
    audio = LocalFileField(required=True, extension='.mp3', dirname=os.path.join(CURRENT_DIR, '../data/mp3/'))
    ebook_licence = fields.String(required=True)
    ebook_page = fields.Url(required=True)
    ebook_parts = fields.List(fields.String, required=True)
    ebook = LocalFileField(required=True, extension='.epub', dirname=os.path.join(CURRENT_DIR, '../data/epubs/'))
    language = fields.String(required=True, validate=lambda x: x in ['fr_FR', 'en_US'], error_messages={
        'validator_failed': 'expect language to be one of "fr_FR" or "en_US"',
    })


def read_sources() -> dict:
    with open(os.path.join(os.path.dirname(__file__), '../sources.json')) as f:
        return json.load(f)


def get_source(name: str) -> dict:
    sources = read_sources()
    if name not in sources:
        raise Exception(f'source "{name}" not found')
    source = sources[name]
    data, errors = SourceSchema().load(source, many=False)

    if errors:
        raise Exception(f'source "{name}" misconfigured: {errors}')
    return source


def update_sources(value: dict) -> dict:
    with open(os.path.join(os.path.dirname(__file__), '../sources.json'), 'w') as f:
        return json.dump(value, f, indent=2, sort_keys=True)


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
