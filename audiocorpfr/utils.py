import json
import os
import re
import subprocess
from zipfile import ZipFile
import roman
from bs4 import BeautifulSoup
from typing import Pattern

from num2words import num2words
from nltk.tokenize import sent_tokenize


NORMALIZATIONS = [
    ['M.\u00a0', 'Monsieur '],
    ['M. ', 'Monsieur '],
    ['Mme\u00a0', 'Madame '],
    ['Mme ', 'Madame '],
    ['Mlle\u00a0', 'Mademoiselle '],
    ['Mlle ', 'Mademoiselle '],
    ['Mlles\u00a0', 'Mademoiselles '],
    ['Mlles ', 'Mademoiselles '],
    ['%', 'pourcent'],
    ['arr. ', 'arrondissement '],
    [re.compile('\[\d+\]'), ''],
    ['f’ras', 'feras'],
    ['f’rez', 'ferez'],
    [re.compile(r'\s?:\s?'), '.\n'],
    [re.compile(r'^\s?(-|—|–)\s?'), ''],
    [re.compile(r'("|«)\s?'), ''],
    [re.compile(r'\s?("|»)'), ''],
]
ROMAN_CHARS = 'XVI'
NUMS_REGEX = re.compile("(\d+,?\u00A0?\d+)|(\d+\w+)|(\d)*")
ORDINAL_REGEX = re.compile("(\d+)([ieme|ier|iere]+)")


def get_roman_numbers(ch):

    ro = ''
    ros = 0
    for i in range(len(ch)):
        c = ch[i]
        if c in ROMAN_CHARS:
            if len(ro) == 0 and not ch[i-1].isalpha():
                ro = c
                ros = i
            else:
                if len(ro) > 0 and ch[i-1] in ROMAN_CHARS:
                    ro += c
        else:
            if len(ro) > 0:
                if not c.isalpha():
                    yield ch[ros-1], ch[i], ro
                ro = ''
                ros = i

    if len(ro) > 0:
        yield ch[ros-1], '', ro


def get_numbers(text):
    return NUMS_REGEX.split(text)


def cut_audio(input_path: str, from_: float, to: float, output_path: str):
    assert to > from_
    subprocess.call(f'ffmpeg -loglevel quiet -y -i {input_path} -ss {from_} -to {to} -c copy {output_path}'.split(' '))


def maybe_normalize(value, mapping=NORMALIZATIONS):
    for norm in mapping:
        if type(norm[0]) == str:
            value = value.replace(norm[0], norm[1])
        elif isinstance(norm[0], Pattern):
            value = norm[0].sub(norm[1], value)
        else:
            print('UNEXPECTED', type(norm[0]), norm[0])

    for ro_before, ro_after, ro in get_roman_numbers(value):
        try:
            value = value.replace(ro_before + ro + ro_after, ro_before + str(roman.fromRoman(ro)) + ro_after)
        except roman.InvalidRomanNumeralError as ex:
            pass

    return value


def file_extension(path_to_file):
    filename, extension = os.path.splitext(path_to_file)
    return extension


def filter_numbers(inp):
    finalinp = ''
    for e in get_numbers(inp):
        if not e:
            continue
        newinp = e
        try:
            ee = ''.join(e.split())
            if int(e) > 0:
                newinp = num2words(int(ee), lang='fr')
        except ValueError:
            try:
                ee = ''.join(e.replace(',', '.').split())
                if float(ee):
                    newinp = num2words(float(ee), lang='fr')
            except ValueError:
                matches = ORDINAL_REGEX.match(e)
                if matches:
                    newinp = num2words(int(matches.group(1)), ordinal=True, lang='fr')

        finalinp += newinp

    return finalinp


def extract_sentences(full_text):
    for line in full_text.split('\n'):
        line = line.strip()
        if line:
            for sentence in sent_tokenize(line, language='french'):
                sentence_txt = sentence.strip()
                if sentence_txt:
                    yield sentence_txt


def cleanup_document(full_text):
    full_text = full_text.strip()

    # remove chapter number
    def replace_chapter_number(match):
        string = match.group(1)
        num = str(roman.fromRoman(string))
        return f'Chapitre {num},'

    full_text = re.sub(r'^((?:X|V|I)+)\.', replace_chapter_number, full_text)

    # " ; " => '. '
    def replace_semi_colons(match):
        upper_char = match.group(1).upper()
        return f'. {upper_char}'

    full_text = re.sub(r'\s+?;\s+?(\w)', replace_semi_colons, full_text)

    def normalize_line(line):
        if line:
            line = maybe_normalize(line, mapping=NORMALIZATIONS)
            line = filter_numbers(line)

        return line.strip()

    lines = [normalize_line(l) for l in extract_sentences(full_text)]

    return '\n'.join(l for l in lines if l)


def read_sources() -> dict:
    with open(os.path.join(os.path.dirname(__file__), '../sources.json')) as f:
        return json.load(f)


def update_sources(value: dict) -> dict:
    with open(os.path.join(os.path.dirname(__file__), '../sources.json'), 'w') as f:
        return json.dump(value, f, indent=2, sort_keys=True)


def read_epub(path_to_epub, path_to_xhtmls=None):
    if not isinstance(path_to_xhtmls, list) and not isinstance(path_to_xhtmls, tuple):
        path_to_xhtmls = [path_to_xhtmls]
    html_txt = ''
    with ZipFile(path_to_epub) as myzip:
        for path_to_xhtml in path_to_xhtmls:
            with myzip.open(os.path.join('OEBPS', path_to_xhtml)) as f:
                html_doc = f.read()
            soup = BeautifulSoup(html_doc, 'html.parser')
            html_txt += '\n' + soup.body.get_text(separator='\n')

    return cleanup_document(html_txt)
