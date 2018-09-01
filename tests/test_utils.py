import os

import pytest
from audiocorpfr import utils


CURRENT_DIR = os.path.dirname(__file__)


@pytest.mark.parametrize('filename, expected', [
    ('path/to/file.wav', '.wav'),
])
def test_file_extension(filename, expected):
    assert utils.file_extension(filename) == expected


def test_read_sources():
    assert isinstance(utils.read_sources(), dict)


@pytest.mark.parametrize('paragraph, expected_sentences', [
    ("""
I. Marseille. – L’arrivée.

Le 24 février 1815, la vigie de Notre-Dame de la Garde signala le trois-mâts le Pharaon, venant de Smyrne, Trieste et Naples.
Comme d’habitude, un pilote côtier partit aussitôt du port, rasa le château d’If, et alla aborder le navire entre le cap de Morgion et l’île de Rion.
""", [
        'Chapitre un, Marseille.',
        'L’arrivée.',
        'Le vingt-quatre février mille huit cent quinze, la vigie de Notre-Dame de la Garde signala le trois-mâts le Pharaon, venant de Smyrne, Trieste et Naples.',
        'Comme d’habitude, un pilote côtier partit aussitôt du port, rasa le château d’If, et alla aborder le navire entre le cap de Morgion et l’île de Rion.',
    ]),
    ('XXIV. Éblouissement.', ['Chapitre vingt-quatre, Éblouissement.']),
    ('Aussitôt la plate-forme du fort Saint-Jean s’était couverte de curieux ; car c’est toujours une grande affaire à Marseille que l’arrivée d’un bâtiment.', [
        'Aussitôt la plate-forme du fort Saint-Jean s’était couverte de curieux.',
        'Car c’est toujours une grande affaire à Marseille que l’arrivée d’un bâtiment.',
    ]),
    ('25.000', ['vingt-cinq mille']),
])
def test_cleanup_document(paragraph, expected_sentences):
    assert utils.cleanup_document(paragraph).split('\n') == expected_sentences


@pytest.mark.parametrize('source, expected_errors', [
    ({}, {
        'audio': ['Missing data for required field.'],
        'audio_licence': ['Missing data for required field.'],
        'audio_page': ['Missing data for required field.'],
        'ebook': ['Missing data for required field.'],
        'ebook_licence': ['Missing data for required field.'],
        'ebook_page': ['Missing data for required field.'],
        'ebook_parts': ['Missing data for required field.']
    }),
    ({
         'audio_licence': 'Creative Commons',
         'audio_page': 'https://www.audiocite.net/livres-audio-gratuits-romans/alexandre-dumas-le-comte-de-monte-cristo.html',
         'audio': 'wrong_extension.foo',
         'ebook_licence': 'Public domain',
         'ebook_page': 'https://www.atramenta.net/lire/le-comte-de-monte-cristo-tome-i/6318',
         'ebook': 'do_not_exists.epub',
         'ebook_parts': ['part1.xhtml'],
     }, {
         'audio': ['expect extension to be .mp3'],
         'ebook': ['file not found'],
     }),
])
def test_validate_source_ko(source: dict, expected_errors: dict):
    data, errors = utils.SourceSchema().load(source, many=False)
    assert expected_errors == errors


@pytest.mark.parametrize('input_, expected_output', [
    ('1', True),
    ('abc', False),
    ('1.1', True),
    ('1,1', True),
])
def test_is_float(input_, expected_output):
    assert expected_output == utils.is_float(input_)


@pytest.mark.parametrize('alignment, silences, fixed_alignment', [
    ([{
        "begin": 0,
        "end": 4.86,
    }, {
        "begin": 4.86,
        "end": 16.28,
    }], [(3.109, 4.909)], [{
        "begin": 0,
        "end": 3.609,
    }, {
        "begin": 4.409,
        "end": 16.28,
    }]),
    ([{
        "begin": 26.247,
        "end": 32.5,
    }, {
        "begin": 32.5,
        "end": 48.618,
    }], [(32.601, 33.487)], [{
        "begin": 26.247,
        "end": 33.101,
    }, {
        "begin": 32.987,
        "end": 48.618,
    }]),
    # Test fragment in silent
    ([{
        "begin": 639.341,
        "end": 640.945,
        "text": "Ah\u00a0!"
    }, {
        "begin": 640.674,
        "end": 640.945,
        "text": "ah\u00a0!"
    }, {
        "begin": 640.674,
        "end": 643.661,
        "text": "a-t-il dit, je la connais."
    }], [
         (638.982, 639.841),
         (640.445, 641.174),
         (641.803, 642.375),
     ], [{
        "begin": 639.341,
        "end": 640.945,
        "text": 'Ah\u00a0! ah\u00a0!'
    }, {
        "begin": 640.674,
        "end": 643.661,
        "text": "a-t-il dit, je la connais."
    }]),
])
def test_fix_alignment(alignment, silences, fixed_alignment):
    assert fixed_alignment == utils.fix_alignment(alignment, silences)


@pytest.mark.parametrize('old, new_, merged', [
    # exactly the same
    (
            [dict(begin=1, end=2, text='a', approved=True)],
            [dict(begin=1, end=2, text='a')],
            [dict(begin=1, end=2, text='a', approved=True)],
    ),
    # small change
    (
            [dict(begin=1, end=2, text='a', approved=True)],
            [dict(begin=1.01, end=2, text='a')],
            [dict(begin=1, end=2, text='a', approved=True)],
    ),
    # split
    (
            [
                dict(begin=0, end=1, text='a', approved=True),
                dict(begin=1, end=3, text='b c', approved=True),
                dict(begin=3, end=4, text='d', approved=True),
            ], [
                dict(begin=0, end=1, text='a'),
                dict(begin=1, end=2, text='b'),
                dict(begin=2, end=3, text='c'),
                dict(begin=3, end=4, text='d'),
            ], [
                dict(begin=0, end=1, text='a', approved=True),
                dict(begin=1, end=2, text='b'),
                dict(begin=2, end=3, text='c'),
                dict(begin=3, end=4, text='d', approved=True),
            ],
    ),
    # merge
    (
            [
                dict(begin=0, end=1, text='a', approved=True),
                dict(begin=1, end=2, text='b', approved=True),
                dict(begin=2, end=3, text='c', approved=True),
                dict(begin=3, end=4, text='d', approved=True),
            ], [
                dict(begin=0, end=1, text='a'),
                dict(begin=1, end=3, text='b c'),
                dict(begin=3, end=4, text='d'),
            ], [
                dict(begin=0, end=1, text='a', approved=True),
                dict(begin=1, end=3, text='b c'),
                dict(begin=3, end=4, text='d', approved=True),
            ],
    ),
    # leave "forced" alignments untouched
    (
            [
                dict(begin=0, end=1, text='a', approved=True, end_forced=True),
                dict(begin=2, end=3, text='b', approved=True, begin_forced=True, end_forced=True),
                dict(begin=3, end=4, text='c', approved=True, begin_forced=True),
            ], [
                dict(begin=0, end=1.1, text='a'),
                dict(begin=2.2, end=3.1, text='b'),
                dict(begin=3.1, end=4, text='c'),
            ], [
                dict(begin=0, end=1, text='a', approved=True, end_forced=True),
                dict(begin=2, end=3, text='b', approved=True, begin_forced=True, end_forced=True),
                dict(begin=3, end=4, text='c', approved=True, begin_forced=True),
            ],
    ),
    # no current alignment
    (
            [],
            [dict(begin=1, end=2, text='a')],
            [dict(begin=1, end=2, text='a')],
    ),
])
def test_merge_alignments(old, new_, merged):
    assert merged == utils.merge_alignments(old, new_)


@pytest.mark.parametrize('filename', ['speech.mp3', 'speech.wav'])
def test_get_alignment(filename):
    path_to_mp3 = os.path.join(CURRENT_DIR, f'./assets/{filename}')
    transcript = [
        'Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.',
        'Vous n’avez pas une seule coquetterie à me reprocher à votre égard.',
    ]
    assert utils.get_alignment(path_to_mp3, transcript, force=True) == [
        dict(begin=0, end=6.22, text=transcript[0]),
        dict(begin=6.22, end=9.22, text=transcript[1]),
    ]

