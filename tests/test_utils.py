import pytest
from audiocorpfr import utils


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
    # Test no silent => merge
    ([{
        "begin": 26.247,
        "end": 32.5,
        "text": 'foo'
    }, {
        "begin": 32.5,
        "end": 48.618,
        "text": 'bar'
    }], [], [{
        "begin": 26.247,
        "end": 48.618,
        "text": 'foo bar'
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
    ([
        dict(begin=1, end=2, text='a', approved=True, id=1),
    ], [
        dict(begin=1, end=2, text='a', id=1),
    ], [
        dict(begin=1, end=2, text='a', approved=True, id=1),
    ]),
    # small change
    ([
        dict(begin=1, end=2, text='a', approved=True, id=1),
    ], [
        dict(begin=1.01, end=2, text='a', id=1),
    ], [
        dict(begin=1.01, end=2, text='a', id=1),
    ]),
    # split
    ([
        dict(begin=0, end=1, text='a', approved=True, id=0),
        dict(begin=1, end=3, text='b c', approved=True, id=1),
        dict(begin=3, end=4, text='d', approved=True, id=2),
    ], [
        dict(begin=0, end=1, text='a', id=0),
        dict(begin=1, end=2, text='b', id=1),
        dict(begin=2, end=3, text='c', id=2),
        dict(begin=3, end=4, text='d', id=3),
    ], [
        dict(begin=0, end=1, text='a', id=0, approved=True),
        dict(begin=1, end=2, text='b', id=1),
        dict(begin=2, end=3, text='c', id=2),
        dict(begin=3, end=4, text='d', id=3, approved=True),
    ]),
    # merge
    ([
        dict(begin=0, end=1, text='a', id=0, approved=True),
        dict(begin=1, end=2, text='b', id=1, approved=True),
        dict(begin=2, end=3, text='c', id=2, approved=True),
        dict(begin=3, end=4, text='d', id=3, approved=True),
    ], [
        dict(begin=0, end=1, text='a', id=0),
        dict(begin=1, end=3, text='b c', id=1),
        dict(begin=3, end=4, text='d', id=2),
    ], [
        dict(begin=0, end=1, text='a', id=0, approved=True),
        dict(begin=1, end=3, text='b c', id=1),
        dict(begin=3, end=4, text='d', id=2, approved=True),
    ]),
])
def test_merge_alignments(old, new_, merged):
    assert merged == utils.merge_alignments(old, new_)
