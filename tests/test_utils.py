import os
from datetime import timedelta

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
    ('Aussitôt la plate-forme du fort Saint-Jean s’était couverte de curieux ; car c’est toujours une grande affaire à Marseille que l’arrivée d’un bâtiment.', [
        'Aussitôt la plate-forme du fort Saint-Jean s’était couverte de curieux.',
        'Car c’est toujours une grande affaire à Marseille que l’arrivée d’un bâtiment.',
    ]),
    ('25.000', ['vingt-cinq mille']),
    ('La postérité ne pourra lui faire justice… Pas de gloire, Cesare Bordone !… Allons, c’est fini.', [
        'La postérité ne pourra lui faire justice… Pas de gloire, Cesare Bordone !… Allons, c’est fini.'
    ]),
    ('(foo bar.)', ['foo bar.']),
    ('I\nBicêtre.', ['Chapitre un.', 'Bicêtre.']),
    ('LXCVII.', ['Chapitre quatre-vingt-dix-sept.']),
    ('LIV. La hausse et la baisse.', ['Chapitre cinquante-quatre.', 'La hausse et la baisse.']),
    ('XLVI.', ['Chapitre quarante-six.']),
    ('qui appartient à MM. Morrel et fils.', ['qui appartient à monsieur Morrel et fils.']),
    ('M. Panel.', ['monsieur Panel.']),
    # n° => numéro
    ('No 10', ['Numéro dix']),
    ('rue Coq-Héron, nº treize', ['rue Coq-Héron, numéro treize']),
    # test no split
    ('Ah ! c’est vous, Dantès ! cria l’homme à la barque.', ['Ah ! c’est vous, Dantès ! cria l’homme à la barque.']),
    ('Ah ! Foo bar', ['Ah ! Foo bar']),
    ('Et… demanda', ['Et… demanda']),
    # test split
    ('bord ?\n— Un', ['bord ?', 'Un']),
    # remove parentheses
    ('(foo bar)', ['foo bar']),
    ('(foo bar).', ['foo bar']),
    ('foo. Mais bar', ['foo. Mais bar']),
    ('M.Morel', ['Monsieur Morel']),
    ('Si tu es grinche[15], je ne suis pas ton homme', ['Si tu es grinche, je ne suis pas ton homme']),
    ('— Bonsoir, Chourineur[1].', ['Bonsoir, Chourineur.']),
    ('N° 13', ['Numéro treize']),
    ('c\'est au n° 13', ['c\'est au numéro treize']),
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
        "end": 3.459,
    }, {
        "begin": 4.559,
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
        "end": 32.951,
    }, {
        "begin": 33.137,
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
        "text": 'Ah\u00a0! ah\u00a0!',
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
        dict(begin=0, end=6.32, text=transcript[0]),
        dict(begin=6.32, end=9.32, text=transcript[1]),
    ]


BUILD_ALIGNMENT_TESTS = [
    # baseline
    ('speech.wav', -45, 0.08, [
        'Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.',
        'Vous n’avez pas une seule coquetterie à me reprocher à votre égard.',
    ], [], [
         dict(begin=0., end=5.854, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.'),
         dict(begin=6.002, end=9.32, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
     ]),
    # with existing alignment
    ('speech.wav', -45, 0.08, [
        'Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.',
        'Vous n’avez pas une seule coquetterie à me reprocher à votre égard.',
    ], [
         dict(begin=0, end=6, approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.'),
         dict(begin=5.852, end=9.22, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
     ], [
         dict(begin=0, end=6, approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir, Fernand, répondit Mercédès.'),
         dict(begin=5.852, end=9.212, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
     ]),
    # with deprecated alignment
    ('speech.wav', -45, 0.08, [
        'Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir',
        'Fernand',
        'répondit Mercédès',
        'Vous n’avez pas une seule coquetterie à me reprocher à votre égard.',
    ], [
         dict(begin=0, end=3., approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir'),
         dict(begin=3, end=5, approved=True, text='Fernand, répondit Mercédès.'),
         dict(begin=5.852, end=9.22, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
     ], [
         dict(begin=0, end=3., approved=True, text='Ce n’est pas moi du moins qui vous ai jamais encouragé dans cet espoir'),
         dict(begin=3., end=3.934, text='Fernand'),
         dict(begin=4.082, end=5.854, text='répondit Mercédès'),
         dict(begin=6.002, end=9.2, text='Vous n’avez pas une seule coquetterie à me reprocher à votre égard.'),
     ]),
    # warnings
    ('wrong_cut0.wav', -45, 0.08, [
        'À dix pas en mer la barque se balançait gracieusement sur son ancre.',
        'Alors il savoura quelque temps cette brise fraîche qui lui passait sur le front.',
    ], [], [
         dict(begin=0., end=6.366, text='À dix pas en mer la barque se balançait gracieusement sur son ancre.'),
         dict(warn=True, begin=6.13, end=10.28, text='Alors il savoura quelque temps cette brise fraîche qui lui passait sur le front.'),
     ]),
    ('wrong_cut1.wav', -45, 0.08, [
        'Chapitre trente-deux.',
        'Réveil.',
        'Lorsque Franz revint à lui, les objets extérieurs semblaient une seconde partie de son rêve.',
        'Il se crut dans un sépulcre où pénétrait à peine, comme un regard de pitié, un rayon de soleil.',
    ], [], [
         {'begin': 0., 'end': 1.934, 'text': 'Chapitre trente-deux.'},
         {'begin': 1.954, 'end': 3.214, 'text': 'Réveil.'},
         {'begin': 3.874, 'end': 9.998, 'text': 'Lorsque Franz revint à lui, les objets extérieurs semblaient une seconde partie de son rêve.'},
         {'begin': 10.146, 'end': 17.24, 'text': 'Il se crut dans un sépulcre où pénétrait à peine, comme un regard de pitié, un rayon de soleil.'},
    ]),
    # # LeComteDeMonteCristoT2Chap33 @@ 0:03:56.114000 0:04:10.228000 @@
    # ('8e9ec633.wav', -45, 0.07, [
    #     'Dans une heure elle sera à la porte.',
    #     'Une heure après, effectivement, la voiture attendait les deux jeunes gens.',
    #     'c’était un modeste fiacre que, vu la solennité de la circonstance, on avait élevé au rang de calèche.',
    # ], [], [
    #      dict(begin=0.0, end=2.676, text='Dans une heure elle sera à la porte.'),
    #      dict(warn=True, begin=2.77, end=6.9, text='Une heure après, effectivement, la voiture attendait les deux jeunes gens.'),
    #      dict(begin=6.738, end=14.08, text='c’était un modeste fiacre que, vu la solennité de la circonstance, on avait élevé au rang de calèche.'),
    #  ]),
    # # LeComteDeMonteCristoT2Chap33 @@ 0:15:55.986000 0:16:09.286000 @@
    # ('ba896654.wav', -45, 0.07, [
    #     'Ah çà, fit Franz, arrêtant maître Pastrini au moment où il ouvrait la bouche, vous dites que vous avez connu Luigi Vampa tout enfant.',
    #     'C’est donc encore un jeune homme ?',
    #     'Comment, un jeune homme ! je crois bien.',
    # ], [], [
    #     dict(begin=0.0, end=9.158, text='Ah çà, fit Franz, arrêtant maître Pastrini au moment où il ouvrait la bouche, vous dites que vous avez connu Luigi Vampa tout enfant.'),
    #     dict(begin=8.96, end=10.182, text='C’est donc encore un jeune homme ?'),
    #     dict(begin=9.984, end=13.28, warn=True, text='Comment, un jeune homme ! je crois bien.'),
    # ]),
    # LeComteDeMonteCristoT2Chap33 @@ 0:52:56.150000 0:53:08.984000 @@
    ('e3eb48ec.wav', -45, 0.07, [
        'Le désires-tu aussi ardemment que tu le dis ? Oui.',
        'Eh bien tu l’auras !',
        'La jeune fille, étonnée, leva la tête pour le questionner. Mais son visage était si sombre et si terrible que la parole se glaça sur ses lèvres.',
    ], [], [
         dict(begin=0.0, end=3.55, text='Le désires-tu aussi ardemment que tu le dis ? Oui.'),
         dict(begin=3.816, end=5.086, text='Eh bien tu l’auras !'),
         dict(begin=5.352, end=12.8, text='La jeune fille, étonnée, leva la tête pour le questionner. Mais son visage était si sombre et si terrible que la parole se glaça sur ses lèvres.'),
     ]),
    # LeComteDeMonteCristoT2Chap33 @@ 0:53:08.950000 0:53:20.880000 @@
    ('39a9d8af.wav', -45, 0.07, [
        'D’ailleurs, en disant ces paroles, Luigi s’était éloigné.',
        'Teresa le suivit des yeux dans la nuit tant qu’elle put l’apercevoir.',
        'Puis, lorsqu’il eut disparu, elle rentra chez elle en soupirant.',
    ], [], [
         dict(begin=0.0, end=5.214, text='D’ailleurs, en disant ces paroles, Luigi s’était éloigné.'),
         dict(warn=True, begin=4.968, end=8.286, text='Teresa le suivit des yeux dans la nuit tant qu’elle put l’apercevoir.'),
         dict(begin=8.296, end=11.92, text='Puis, lorsqu’il eut disparu, elle rentra chez elle en soupirant.'),
     ]),
    # LeComteDeMonteCristoT2Chap33 @@ 0:53:54.770000 0:54:11.570000 @@
    ('ce69d5cb.wav', -45, 0.07, [
        'Un jeune paysan s’était élancé dans l’appartement, l’avait prise dans ses bras, et, avec une force et une adresse surhumaines l’avait transportée sur le gazon de la pelouse, où elle s’était évanouie.',
        'Lorsqu’elle avait repris ses sens, son père était devant elle.',
        'Tous les serviteurs l’entouraient, lui portant des secours.',
    ], [], [
        dict(begin=0.0, end=10.206, text='Un jeune paysan s’était élancé dans l’appartement, l’avait prise dans ses bras, et, avec une force et une adresse surhumaines l’avait transportée sur le gazon de la pelouse, où elle s’était évanouie.'),
        dict(begin=10.088, end=13.534, text='Lorsqu’elle avait repris ses sens, son père était devant elle.'),
        dict(begin=13.544, end=16.8, text='Tous les serviteurs l’entouraient, lui portant des secours.'),
    ]),
    # LeComteDeMonteCristoT2Chap34 @@ 0:12:48.616000 0:13:03.198000 @@
    ('8d4d6e06.wav', -45, 0.07, [
        'Laissez-moi donc faire.',
        'À merveille. Mais si vous échouez, nous nous tiendrons toujours prêts.',
        'Tenez-vous toujours prêts, si c’est votre plaisir mais soyez certain que j’aurai sa grâce.',
    ], [], [
         dict(begin=0.0, end=3.806, text='Laissez-moi donc faire.'),
         dict(begin=3.688, end=8.286, text='À merveille. Mais si vous échouez, nous nous tiendrons toujours prêts.'),
         dict(begin=8.68, end=14.56, text='Tenez-vous toujours prêts, si c’est votre plaisir mais soyez certain que j’aurai sa grâce.'),
     ]),
    # LeComteDeMonteCristoT2Chap34 @@ 0:17:51.210000 0:18:22.946000 @@
    ('0095e8cf.wav', -45, 0.07, [
        'Il l’avait donc laissé s’éloigner, comme on l’a vu, mais en se promettant, s’il le rencontrait une autre fois, de ne pas laisser échapper cette seconde occasion comme il avait fait de la première.',
        'Franz était trop préoccupé pour bien dormir.',
        'Sa nuit fut employée à passer et repasser dans son esprit toutes les circonstances qui se rattachaient à l’homme de la grotte et à l’inconnu du Colisée, et qui tendaient à faire de ces deux personnages le même individu.',
    ], [], [
        dict(begin=0.0, end=11.544, text='Il l’avait donc laissé s’éloigner, comme on l’a vu, mais en se promettant, s’il le rencontrait une autre fois, de ne pas laisser échapper cette seconde occasion comme il avait fait de la première.'),
        dict(begin=12.066, end=16.152, text='Franz était trop préoccupé pour bien dormir.'),
        dict(begin=16.418, end=31.72, text='Sa nuit fut employée à passer et repasser dans son esprit toutes les circonstances qui se rattachaient à l’homme de la grotte et à l’inconnu du Colisée, et qui tendaient à faire de ces deux personnages le même individu.'),
    ]),

    # LeComteDeMonteCristoT2Chap34 @@ 0:29:32.520000 0:29:55.780000 @@
    # ('88296de3.wav', -45, 0.07, [
    #     'Derrière elle, dans l’ombre, se dessinait la forme d’un homme dont il était impossible de distinguer le visage.',
    #     'Franz interrompit la conversation d’Albert et de la comtesse pour demander à cette dernière si elle connaissait la belle Albanaise qui était si digne d’attirer non seulement l’attention des hommes, mais encore des femmes.',
    #     'Non, dit-elle.',
    # ], [], [
    #      dict(begin=0.0, end=8.926, text='Derrière elle, dans l’ombre, se dessinait la forme d’un homme dont il était impossible de distinguer le visage.'),
    #      dict(warn=True, begin=8.808, end=20.702, text='Franz interrompit la conversation d’Albert et de la comtesse pour demander à cette dernière si elle connaissait la belle Albanaise qui était si digne d’attirer non seulement l’attention des hommes, mais encore des femmes.'),
    #      dict(begin=21.224, end=23.24, text='Non, dit-elle.'),
    #  ]),

    # LeComteDeMonteCristoT2Chap34 @@ 0:35:44.490000 0:36:00.864000 @@
    ('37bfa0dc.wav', -45, 0.07, [
        'Il faut que je sache qui il est, dit Franz en se levant.',
        'Oh ! non, s’écria la comtesse.',
        'Non, ne me quittez pas, je compte sur vous pour me reconduire, et je vous garde.',
        'Comment ! véritablement, lui dit Franz en se penchant à son oreille, vous avez peur ?',
    ], [], [
         dict(begin=0.0, end=3.678, text='Il faut que je sache qui il est, dit Franz en se levant.'),
         dict(warn=True, begin=3.816, end=10.206, text='Oh ! non, s’écria la comtesse. Non, ne me quittez pas, je compte sur vous pour me reconduire, et je vous garde.'),
         dict(warn=True, begin=10.344, end=16.36, text='Comment ! véritablement, lui dit Franz en se penchant à son oreille, vous avez peur ?'),
     ]),

    # LeComteDeMonteCristoT2Chap34 @@ 0:44:54.760000 0:45:05.502000 @@
    ('5a8da8cc.wav', -45, 0.07, [
        'Il aura l’honneur de s’informer auprès de ces messieurs à quelle heure ils seront visibles.',
        'Ma foi, dit Albert à Franz, il n’y a rien à y reprendre, tout y est.',
        'Dites au comte, répondit Franz, que c’est nous qui aurons l’honneur de lui faire notre visite.',
    ], [], [
         dict(begin=0.0, end=3.014, text='Il aura l’honneur de s’informer auprès de ces messieurs à quelle heure ils seront visibles.'),
         dict(begin=2.688, end=4.83, text='Ma foi, dit Albert à Franz, il n’y a rien à y reprendre, tout y est.'),
         dict(begin=5.736, end=10.72,
              text='Dites au comte, répondit Franz, que c’est nous qui aurons l’honneur de lui faire notre visite.'),
     ]),

    # # LeComteDeMonteCristoT2Chap35 @@ 0:02:42.850000 0:02:56.920000 @@
    # ('ab6fdc52.wav', -45, 0.07, [
    #     'Oui, répondit Franz, voyant qu’il venait de lui-même où il voulait l’amener.',
    #     'Attendez, attendez, je crois avoir dit hier à mon intendant de s’occuper de cela.',
    #     'Peut-être pourrai-je vous rendre encore ce petit service.',
    # ], [], [
    #      dict(begin=0.0, end=3.934, text='Oui, répondit Franz, voyant qu’il venait de lui-même où il voulait l’amener.'),
    #      dict(begin=3.688, end=11.334, text='Attendez, attendez, je crois avoir dit hier à mon intendant de s’occuper de cela.'),
    #      dict(begin=11.264, end=14.04, text='Peut-être pourrai-je vous rendre encore ce petit service.'),
    #  ]),

]


@pytest.mark.parametrize('filename, noise_level, min_duration, transcript, existing_alignment, expected', BUILD_ALIGNMENT_TESTS)
def test_build_alignment(filename, noise_level, min_duration, transcript, existing_alignment, expected):
    path_to_audio = os.path.join(CURRENT_DIR, './assets/', filename)
    generated = utils.build_alignment(
        transcript=transcript,
        path_to_audio=path_to_audio,
        existing_alignment=existing_alignment,
        silences=ffmpeg.list_silences(
            path_to_audio,
            noise_level=noise_level,
            min_duration=min_duration,
            force=True),
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


@pytest.mark.parametrize('left_fragment, right_fragment, silences, expected', [
    (
            dict(begin=0, end=4),
            dict(begin=3, end=7),
            [[0, 0.1], [1, 2], [3, 4], [5, 6], [8, 9]],
            ([1, 2], [3, 4], [5, 6]),
    ),
    (
            dict(begin=0, end=1),
            dict(begin=2, end=3),
            [[1, 2]],
            (None, [1, 2], None),
    ),
    (
            dict(begin=0, end=3),
            dict(begin=2, end=5),
            [[1, 4]],
            (None, [1, 4], None),
    ),
])
def test_transition_silences(left_fragment, right_fragment, silences, expected):
    assert expected == utils.transition_silences(left_fragment, right_fragment, silences)


@pytest.mark.parametrize('td, expected', [
    (timedelta(seconds=10), '00:00:10.000'),
    (timedelta(seconds=10.123), '00:00:10.123'),
    (timedelta(days=3.141592), '75:23:53.548'),
    (timedelta(days=10), '240:00:00.000'),
])
def test_format_timedelta(td, expected):
    assert expected == utils.format_timedelta(td)
