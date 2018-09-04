import os

import pytest
from audiocorp import utils, ffmpeg

CURRENT_DIR = os.path.dirname(__file__)


@pytest.mark.parametrize('filename, expected', [
    ('path/to/file.wav', '.wav'),
])
def test_file_extension(filename, expected):
    assert utils.file_extension(filename) == expected


@pytest.mark.parametrize('paragraph, expected_sentences', [
    ("""
I. Marseille. – L’arrivée.

Le 24 février 1815, la vigie de Notre-Dame de la Garde signala le trois-mâts le Pharaon, venant de Smyrne, Trieste et Naples.
Comme d’habitude, un pilote côtier partit aussitôt du port, rasa le château d’If, et alla aborder le navire entre le cap de Morgion et l’île de Rion.
""", [
        'Chapitre un.',
        'Marseille.',
        'L’arrivée.',
        'Le vingt-quatre février mille huit cent quinze, la vigie de Notre-Dame de la Garde signala le trois-mâts le Pharaon, venant de Smyrne, Trieste et Naples.',
        'Comme d’habitude, un pilote côtier partit aussitôt du port, rasa le château d’If, et alla aborder le navire entre le cap de Morgion et l’île de Rion.',
    ]),
    ('XXIV. Éblouissement.', ['Chapitre vingt-quatre.', 'Éblouissement.']),
    ('Aussitôt la plate-forme du fort Saint-Jean s’était couverte de curieux ; car c’est toujours une grande affaire à Marseille que l’arrivée d’un bâtiment.', [
        'Aussitôt la plate-forme du fort Saint-Jean s’était couverte de curieux.',
        'Car c’est toujours une grande affaire à Marseille que l’arrivée d’un bâtiment.',
    ]),
    ('25.000', ['vingt-cinq mille']),
    ('La postérité ne pourra lui faire justice… Pas de gloire, Cesare Bordone !… Allons, c’est fini.', [
        'La postérité ne pourra lui faire justice…',
        'Pas de gloire, Cesare Bordone !…',
        'Allons, c’est fini.'
    ]),
    ('(foo bar.)', ['foo bar.']),
    ('I\nBicêtre.', ['Chapitre un.', 'Bicêtre.']),
    ('LXCVII.', ['Chapitre quatre-vingt-dix-sept.']),
    ('XLVI.', ['Chapitre quarante-six.']),
    ('qui appartient à MM. Morrel et fils.', ['qui appartient à monsieur Morrel et fils.']),
    ('M. Panel.', ['monsieur Panel.']),
    # n° => numéro
    ('No 10', ['Numéro dix']),
    ('rue Coq-Héron, nº treize', ['rue Coq-Héron, numéro treize']),
    # test no split
    ('Ah ! c’est vous, Dantès ! cria l’homme à la barque.', ['Ah ! c’est vous, Dantès ! cria l’homme à la barque.']),
    ('Et… demanda', ['Et… demanda']),
    # test split
    ('bord ?\n— Un', ['bord ?', 'Un']),
])
def test_cleanup_document(paragraph, expected_sentences):
    assert expected_sentences == utils.cleanup_document(paragraph).split('\n')


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
    (
        [
            dict(begin=1, end=2, text='a'),  # NB: in the middle of first silence
            dict(begin=4, end=5, text='b'),
        ], [
            [0, 3],  # NB: contains first speech
            [6, 7],
        ], [
            dict(begin=1, end=5, text='a b'),
        ]
    ),
    (
        [
            dict(begin=1, end=2, text='a'),  # NB: in the middle of first silence
            dict(begin=1, end=5, text='b'),
        ], [], [
            dict(begin=1, end=5, text='a b'),
        ]
    ),
])
def test_fix_alignment(alignment, silences, fixed_alignment):
    assert fixed_alignment == utils.fix_alignment(alignment, silences)


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


@pytest.mark.parametrize('transcript, existing_alignment, expected', [
    # baseline
    ([
        'Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.',
        'Vous n’avez pas une seule coquetterie à me reprocher à votre égard.',
    ], [], [
        dict(begin=0, end=6.004, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.'),
        dict(begin=5.842, end=9.22, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
    ]),
    # with existing alignment
    ([
        'Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.',
        'Vous n’avez pas une seule coquetterie à me reprocher à votre égard.',
    ], [
        dict(begin=0, end=6, approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.'),
        dict(begin=5.842, end=9.22, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
    ], [
        dict(begin=0, end=6, approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.'),
        dict(begin=5.842, end=9.102, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
    ]),
    # with deprecated alignment
    ([
        'Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir',
        'Fernand',
        'répondit Mercédès',
        'Vous n’avez pas une seule coquetterie à me reprocher à votre égard.',
    ], [
        dict(begin=0, end=3, approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir'),
        dict(begin=3, end=5, approved=True, text='Fernand, répondit Mercédès.'),
        dict(begin=5.842, end=9.22, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
    ], [
        dict(begin=0, end=3, approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir'),
        dict(begin=3, end=4.084, text='Fernand'),
        dict(begin=3.922, end=06.004, text='répondit Mercédès'),
        dict(begin=5.842, end=9.1, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
    ]),
])
def test_build_alignment(transcript, existing_alignment, expected):
    path_to_audio = os.path.join(CURRENT_DIR, './assets/speech.wav')
    generated = utils.build_alignment(
        transcript=transcript,
        path_to_audio=path_to_audio,
        existing_alignment=existing_alignment,
        silences=ffmpeg.list_silences(path_to_audio, noise_level=-45, min_duration=0.07),
        generate_labels=True
    )
    assert generated == expected


@pytest.mark.parametrize('target, others, expected', [
    (
            dict(begin=1, end=2),
            [dict(begin=3, end=4), dict(begin=5, end=6)],
            dict(begin=3, end=4),
    ),
    (
            dict(begin=2, end=3),
            [dict(begin=0, end=1), dict(begin=5, end=6)],
            dict(begin=0, end=1),
    ),
])
def test_get_closest_fragment(target, others, expected):
    assert expected == utils.get_closest_fragment(target, others)