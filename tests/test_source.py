from datetime import timedelta

import pytest
from audiocorp import source


@pytest.mark.parametrize('data, expected_errors', [
    ({}, {
        'audio': ['Missing data for required field.'],
        'audio_licence': ['Missing data for required field.'],
        'audio_page': ['Missing data for required field.'],
        'ebook': ['Missing data for required field.'],
        'ebook_licence': ['Missing data for required field.'],
        'ebook_page': ['Missing data for required field.'],
        'ebook_parts': ['Missing data for required field.'],
        'language': ['Missing data for required field.'],
        'speaker': ['Missing data for required field.'],
    }),
    ({
         'audio_licence': 'Creative Commons',
         'audio_page': 'https://www.audiocite.net/livres-audio-gratuits-romans/alexandre-dumas-le-comte-de-monte-cristo.html',
         'audio': 'wrong_extension.foo',
         'ebook_licence': 'Public domain',
         'ebook_page': 'https://www.atramenta.net/lire/le-comte-de-monte-cristo-tome-i/6318',
         'ebook': 'do_not_exists.epub',
         'ebook_parts': ['part1.xhtml'],
         'language': 'foo_BAR',
         'speaker': 'Foo Bar',
    }, {
         'audio': ['expect extension to be .mp3'],
         'ebook': ['file not found'],
         'language':  ['expect language to be one of "fr_FR" or "en_US"'],
    }),
])
def test_validate_source_ko(data: dict, expected_errors: dict):
    data, errors = source.SourceSchema().load(data, many=False)
    assert expected_errors == errors


def test_all():
    assert isinstance(source.read_sources(), dict)


def test_source_info():
    assert source.source_info('LeComteDeMonteCristoT1Chap1') == {
        'approved_count': 235,
        'approved_duration': timedelta(0, 1197, 613000),
        'progress': 1.,
        'status': 'DONE',
    }
