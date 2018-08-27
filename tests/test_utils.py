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
