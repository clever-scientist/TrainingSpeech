import json
import os
import re
import tempfile
from _sha1 import sha1
from collections import defaultdict
from copy import deepcopy
from itertools import groupby
from zipfile import ZipFile
import roman
from bs4 import BeautifulSoup
from typing import Pattern, List, Tuple
from num2words import num2words
from nltk.tokenize import sent_tokenize
from aeneas.executetask import ExecuteTask
from aeneas.task import Task
from datadiff import diff

from audiocorp import sox
from audiocorp.exceptions import WrongCutException

EPS = 1e-3
CURRENT_DIR = os.path.dirname(__file__)


# remove chapter number
def replace_chapter_number(match):
    string = match.group(1)
    num = str(roman.fromRoman(string))
    return f'Chapitre {num}'


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
    [re.compile(r'(\d{2})\.(\d{3})'), r'\1\2'],
    [re.compile(r'^\((.*)\)$'), r'\1'],
    [re.compile(r'^L?((?:X|V|L|I|C)+)(\.|$)'), replace_chapter_number],
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
    full_text = full_text.replace('… ', '…\n')
    for line in full_text.split('\n'):
        line = line.strip()
        if line:
            for sentence in sent_tokenize(line, language='french'):
                sentence_txt = sentence.strip()
                if sentence_txt:
                    yield sentence_txt


def cleanup_document(full_text):
    full_text = full_text.strip()




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


def cleanup_fragment(original: dict) -> dict:
    data = deepcopy(original)
    lines = data.pop('lines')
    data.pop('children')
    data.pop('language')
    data.pop('duration', None)
    data.pop('id', None)
    begin = max(float(data['begin']) - 0.1, 0)
    end = float(data['end']) - 0.1
    data.update(
        begin=round(begin, 3),
        end=round(end, 3),
        text=' '.join(lines),
    )
    return data


def fix_alignment(alignment: List[dict], silences: List[Tuple[float, float]]) -> List[dict]:
    alignment = deepcopy(alignment)

    def get_silences(fragment, margin=0):
        for silence_start, silence_end in silences:
            if fragment['begin'] > silence_start and fragment['end'] < silence_end:
                # wrong cut: a fragment cannot be contained in a silent => merge
                raise WrongCutException
            if silence_start - margin < fragment['end'] < silence_end + margin:
                yield (silence_start, silence_end)
            if silence_start - margin > fragment['end']:
                break

    def merge_fragments(left, right):
        left['merged'] = True  # may have been `right`
        left['end'] = right['end']
        right['begin'] = left['begin']
        full_text = left['text'] + ' ' + right['text']
        right['text'] = left['text'] = full_text

    for i, fragment in enumerate(alignment[:-1]):
        for margin in [0, 0.1, 0.3, 0.6]:
            try:
                overlaps = list(get_silences(fragment, margin=margin))
            except WrongCutException:
                if i == 0:
                    # merge with next
                    merge_fragments(fragment, alignment[i+1])
                else:
                    merge_fragments(alignment[i - 1], fragment)
                break

            if len(overlaps) == 1:
                silence_start, silence_end = overlaps[0]
                fragment['end'] = round(min(silence_start + 0.5, silence_end), 3)
                alignment[i + 1]['begin'] = round(max(silence_end - 0.5, silence_start), 3)
                break
            elif len(overlaps) == 2:
                # take the second
                silence_start, silence_end = overlaps[1]
                fragment['end'] = round(min(silence_start + 0.5, silence_end), 3)
                alignment[i + 1]['begin'] = round(max(silence_end - 0.5, silence_start), 3)
                break

        if fragment['begin'] >= fragment['end']:
            # impossible => merge with closest
            closest = get_closest_fragment(fragment, alignment[i-1:i] + alignment[i+1:i+2])
            closest_index = alignment.index(closest)
            if closest_index < i:
                merge_fragments(closest, fragment)
            else:
                merge_fragments(fragment, closest)

    return [f for f in alignment if not f.get('merged')]


def get_closest_fragment(target, others):
    target_center = target['end'] - target['begin']
    return sorted(others, key=lambda x: min(abs(x['begin'] - target_center), abs(x['end'] - target_center)))[0]


def hash_file(file_obj, blocksize=65536):
    hash_ = sha1()
    buf = file_obj.read(blocksize)
    while len(buf) > 0:
        hash_.update(buf)
        buf = file_obj.read(blocksize)
    return hash_.hexdigest()


def is_float(x: str):
    if isinstance(x, str):
        x = x.replace(',', '.').replace(' ', '')
    try:
        float(x)
        return True
    except ValueError:
        return False


def get_alignment(path_to_audio_file: str, transcript: List[str], force=False, language='fr_FR') -> List[dict]:
    # see https://github.com/readbeyond/aeneas/blob/9d95535ad63eef4a98530cfdff033b8c35315ee1/aeneas/ttswrappers/espeakngttswrapper.py#L45  # noqa
    language = {
        'fr_FR': 'fra',
        'en_US': 'eng',
    }[language]
    full_transcript = ' '.join(transcript)
    full_transcript_hash = sha1(full_transcript.encode()).hexdigest()
    path_to_transcript = os.path.join(CURRENT_DIR, f'/tmp/{full_transcript_hash}.txt')

    with open(path_to_audio_file, 'rb') as f:
        audio_file_hash = hash_file(f)

    with open(path_to_transcript, 'w') as f:
        f.writelines('\n'.join(transcript))

    path_to_alignment_tmp = os.path.join(CURRENT_DIR, f'/tmp/{full_transcript_hash}_{audio_file_hash}.json')

    if force or not os.path.isfile(path_to_alignment_tmp):
        # build alignment
        task = Task(f'task_language={language}|os_task_file_format=json|is_text_type=plain')
        task.audio_file_path_absolute = os.path.abspath(path_to_audio_file)
        task.text_file_path_absolute = path_to_transcript
        task.sync_map_file_path_absolute = path_to_alignment_tmp
        executor = ExecuteTask(task=task)
        executor.execute()
        task.output_sync_map_file()

    with open(path_to_alignment_tmp) as source:
        return [cleanup_fragment(f) for f in json.load(source)['fragments']]


def get_fragment_hash(fragment: dict):
    hash_ = sha1(fragment['text'].encode()).hexdigest()
    return f'{hash_}_{fragment["begin"]}_{fragment["end"]}'


def build_alignment(transcript: List[str], path_to_audio: str, existing_alignment: List[dict], silences: List[Tuple[float, float]], generate_labels=False, language='fr_FR'):

    if any(f.get('approved') or f.get('disabled') for f in existing_alignment):
        # remove approved but deprecated alignments
        transcript_diff = diff([f['text'] for f in existing_alignment], transcript)
        t_i = f_i = 0
        last_deleted_fragment_index = None
        alignment_transcript_mapping = defaultdict(list)
        for change, items in transcript_diff.diffs:
            if change == 'context':
                f_i = items[0]
                t_i = items[2]
                continue
            elif change == 'equal':
                for item in items:
                    alignment_transcript_mapping[f_i].append(t_i)
                    t_i += 1
                    f_i += 1
                continue
            elif change == 'delete':
                for item in items:
                    if existing_alignment[f_i]['text'] != item:
                        f_i += 1
                    assert existing_alignment[f_i]['text'] == item
                    existing_alignment[f_i].pop('approved', None)
                    existing_alignment[f_i].pop('disabled', None)
                    last_deleted_fragment_index = f_i
                    if f_i not in alignment_transcript_mapping:
                        alignment_transcript_mapping[f_i] = []
                    f_i += 1
                continue
            elif change == 'insert':
                for item in items:
                    if transcript[t_i] != item:
                        t_i += 1
                    assert transcript[t_i] == item
                    alignment_transcript_mapping[last_deleted_fragment_index].append(t_i)
                    t_i += 1
                continue
            elif change == 'context_end_container':
                continue
            raise NotImplementedError

        alignment = []
        current_index = 0
        for approved, group in groupby(existing_alignment, key=lambda f: f.get('approved') or f.get('disabled')):
            group = list(group)
            if approved:
                current_index += len(group)
                alignment += group
                continue

            group_start = group[0]['begin']
            group_end = group[-1]['end']

            with tempfile.NamedTemporaryFile(suffix='.wav') as file_:
                sox.trim(path_to_audio, file_.name, from_=group_start, to=group_end)
                sub_alignment_transcript = []
                for fragment in group:
                    if current_index in alignment_transcript_mapping:
                        sub_alignment_transcript += [
                            transcript[i]
                            for i in alignment_transcript_mapping[current_index]
                        ]
                    else:
                        sub_alignment_transcript += [fragment['text']]
                    current_index += 1
                sub_alignment = build_alignment(
                    transcript=sub_alignment_transcript,
                    path_to_audio=file_.name,
                    existing_alignment=[],
                    silences=[
                        [max(s - group_start, 0), e - group_start]
                        for s, e in silences
                        if e > group_start and s < group_end
                    ],
                    generate_labels=False,
                )
            for fragment in sub_alignment:
                fragment['begin'] = round(fragment['begin'] + group_start, 3)
                fragment['end'] = round(fragment['end'] + group_start, 3)
            alignment += sub_alignment
    else:
        existing_alignment = get_alignment(path_to_audio_file=path_to_audio, transcript=transcript, language=language)

        alignment = fix_alignment(existing_alignment, silences)

        if any(f['end'] - f['begin'] <= 0 for f in alignment):
            lines = ', '.join([str(i + 1) for i, f in enumerate(alignment) if f['end'] - f['begin'] <= 0])
            raise Exception(f'lines {lines} led to empty or negative alignment')

    if generate_labels:
        # Generate Audacity labels for DEBUG purpose
        path_to_silences_labels = f'/tmp/silences_labels.txt'
        with open(path_to_silences_labels, 'w') as fragment:
            fragment.writelines('\n'.join([
                f'{s}\t{e}\tsilence{i+1:03d}'
                for i, (s, e) in enumerate(silences)
            ]) + '\n')

        path_to_alignment_labels = f'/tmp/alignments_labels.txt'
        with open(path_to_alignment_labels, 'w') as labels_f:
            labels_f.writelines('\n'.join([
                f'{f["begin"]}\t{f["end"]}\t#{i+1:03d}:{f["text"]}'
                for i, f in enumerate(alignment)
            ]) + '\n')

        path_to_original_alignment_labels = f'/tmp/original_alignments_labels.txt'
        with open(path_to_original_alignment_labels, 'w') as labels_f:
            labels_f.writelines('\n'.join([
                f'{f["begin"]}\t{f["end"]}\t#{i+1:03d}:{f["text"]}'
                for i, f in enumerate(existing_alignment)
            ]) + '\n')

    return alignment
