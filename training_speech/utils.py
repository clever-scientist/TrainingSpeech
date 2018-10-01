import json
import os
import re
import tempfile
from _sha1 import sha1
from collections import defaultdict
from copy import deepcopy
from datetime import timedelta
from itertools import groupby
from zipfile import ZipFile
import roman
from bs4 import BeautifulSoup
from typing import Pattern, List, Tuple, Iterator
from num2words import num2words
from nltk.tokenize import sent_tokenize
from aeneas.executetask import ExecuteTask
from aeneas.task import Task
from datadiff import diff

from training_speech import sox
from training_speech.exceptions import WrongCutException

EPS = 1e-3
CURRENT_DIR = os.path.dirname(__file__)
CACHE_DIR = '/tmp/.training_speech/'
NO_SPLIT_TOKENS = {'Ah !', 'Oh !', 'Eh !', 'Mais….', 'Mais…', 'Mais', 'Mais.'}
DEFAULT_VAD_MODE = 3
DEFAULT_VAD_FRAME_DURATION = 20
CLEANUP_REG = re.compile(r'\s(!?.…)')


if not os.path.isdir(CACHE_DIR):
    os.mkdir(CACHE_DIR)


# remove chapter number
def replace_chapter_number(match):
    string = match.group(1)
    try:
        string = str(roman.fromRoman(string))
    except roman.InvalidRomanNumeralError:
        if string.startswith('L'):
            string = str(roman.fromRoman(string[1:]))
    return f'Chapitre {string}.'


def replace_semi_colons(match):
    upper_char = match.group(1).upper()
    return f'. {upper_char}'


NORMALIZATIONS = [
    [re.compile(r'(?:!|\?)(?:—|-)([A-Z])'), r'!\n\1'],
    [re.compile(r'\n?\[\d+\]\n?'), ''],
    [re.compile(r'^((?:X|V|L|I|C)+)(\s–|\.|$)'), replace_chapter_number],
    [re.compile(r'(^| )(n)(?:°|º|°)(\s)?', flags=re.IGNORECASE), r'\1\2uméro '],
    [re.compile(r'(^| )MM?\. ([A-Z]{1})'), r'\1monsieur \2'],
    [re.compile(r'^No '), 'Numéro '],
    ['M.\u00a0', 'Monsieur '],
    [re.compile(r'(^| )M\.([A-Z])'), r'\1Monsieur \2'],
    ['M. ', 'Monsieur '],
    ['Mme\u00a0', 'Madame '],
    ['Mme ', 'Madame '],
    ['Mlle\u00a0', 'Mademoiselle '],
    ['Mlle ', 'Mademoiselle '],
    ['Mlles\u00a0', 'Mademoiselles '],
    ['Mlles ', 'Mademoiselles '],
    ['%', 'pourcent'],
    ['arr. ', 'arrondissement '],
    ['f’ras', 'feras'],
    ['f’rez', 'ferez'],
    [' ', ' '],  # remove non-breaking space
    [re.compile(r'\s?:\s?'), '.\n'],
    [re.compile(r'^\s?(-|—|–|—)\s?'), ''],
    [re.compile(r'("|«)\s?'), ''],
    [re.compile(r'\s?("|»)'), ''],
    [re.compile(r'(\d{2})\.(\d{3})'), r'\1\2'],
    [re.compile(r'^\((.*)\)\.?$'), r'\1'],
    [re.compile(r'\s+?;\s+?(\w)'), replace_semi_colons],
    [re.compile(r'\s\((.*)\),?\s'), r', \1, '],
]
ROMAN_CHARS = 'XVI'
NUMS_REGEX = re.compile("(\d+,?\u00A0?\d+)|(\d+\w+)|(\d)+")
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
    full_text = full_text.replace('… ', '…\n').replace('... ', '...\n')
    prev_sentence = None
    for line in full_text.split('\n'):
        line = line.strip()
        if line:
            for sentence in sent_tokenize(line, language='french'):
                sentence = sentence.strip()
                if not sentence:
                    continue
                sentence = maybe_normalize(sentence, mapping=NORMALIZATIONS)

                if prev_sentence and (
                        prev_sentence in NO_SPLIT_TOKENS or
                        (prev_sentence[-1] in '?!…' and sentence[0].lower() == sentence[0]) or
                        sentence.startswith('Voilà tout.')
                ):
                    prev_sentence = f'{prev_sentence} {sentence}'
                    continue

                if prev_sentence:
                    yield prev_sentence

                prev_sentence = sentence

    if prev_sentence:
        yield prev_sentence


def cleanup_document(full_text):
    full_text = full_text.strip()

    full_text = maybe_normalize(full_text, mapping=NORMALIZATIONS)

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
            for s in soup('div'):
                if any(a and a.startswith('note-body-') for a in s.get_attribute_list('id')):
                    s.extract()

            html_txt += '\n' + soup.body.get_text(separator='\n')

    return cleanup_document(html_txt)


def cleanup_fragment(original: dict) -> dict:
    data = deepcopy(original)
    lines = data.pop('lines')
    data.pop('children')
    data.pop('language')
    data.pop('duration', None)
    data.pop('id', None)
    begin = float(data['begin'])
    end = float(data['end'])
    data.update(
        begin=round(begin, 3),
        end=round(end, 3),
        text=' '.join(lines),
    )
    return data


def fix_alignment(alignment: List[dict], silences: List[Tuple[float, float]], separator=None) -> List[dict]:
    alignment = deepcopy(alignment)

    def get_silences(fragment, margin=0) -> List[Tuple[float, float, int]]:
        for i, (silence_start, silence_end) in enumerate(silences):
            if fragment['begin'] > silence_start and fragment['end'] < silence_end:
                # wrong cut: a fragment cannot be contained in a silent => merge
                raise WrongCutException
            if silence_start - margin < fragment['end'] < silence_end + margin:
                yield silence_start, silence_end, i

            if silence_start - margin > fragment['end']:
                break

    def merge_fragments(left, right):
        left['merged'] = True  # may have been `right`
        left['end'] = right['end']
        right['begin'] = left['begin']
        full_text = left['text'] + (separator or ' ') + right['text']
        right['text'] = left['text'] = full_text
        return right

    for i, fragment in enumerate(alignment[:-1]):
        for margin in [0, 0.1, 0.3, 0.5]:
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
                # in the middle of a silence
                silence_start, silence_end, silence_index = overlaps[0]
                fragment['end'] = round(min(silence_start + 0.35, silence_end), 3)
                alignment[i + 1]['begin'] = round(max(silence_end - 0.35, silence_start), 3)
                break
            elif len(overlaps) == 2:
                # take the second
                silence_start, silence_end, _ = overlaps[1]
                fragment['end'] = round(min(silence_start + 0.35, silence_end), 3)
                alignment[i + 1]['begin'] = round(max(silence_end - 0.35, silence_start), 3)
                break
            elif margin == 0.5 and len(overlaps) == 0:
                # No silence detected => merge with next
                merge_fragments(fragment, alignment[i+1])

        if fragment['begin'] >= fragment['end'] and not fragment.get('merged'):
            # impossible => merge with closest
            others = alignment[i - 1:i] + alignment[i + 1:i + 2]
            closest = get_closest_fragment(fragment, [o for o in others if not o.get('merged')])
            closest_index = alignment.index(closest)
            if closest_index < i:
                merge_fragments(closest, fragment)
            else:
                merge_fragments(fragment, closest)

    current = alignment[0]
    for next_ in alignment[1:]:
        if current.get('merged'):
            continue
        if abs(current['begin'] - next_['begin']) < EPS:
            merge_fragments(current, next_)
        current = next_

    # look for warnings
    alignment = [f for f in alignment if not f.get('merged')]
    for prev_fragment, next_fragment in zip(alignment[:-1], alignment[1:]):
        if prev_fragment.get('text') and '***' in prev_fragment['text']:
            prev_fragment['warn'] = True
            continue
        if prev_fragment.get('text') and '***' in next_fragment['text']:
            next_fragment['warn'] = True
            continue

        if (next_fragment['begin'] - prev_fragment['end']) > 1:
            continue

        if next_fragment['end'] - next_fragment['begin'] > 15.5:
            next_fragment['warn'] = True
            continue

        silence_before, silence_between, silence_after = transition_silences(prev_fragment, next_fragment, silences)
        if not silence_between:
            continue

        if (
                silence_before and silence_before[1] - silence_before[0] > 0.1 and
                silence_between[0] - silence_before[1] <= 0.54001 and
                silence_between[1] - silence_between[0] < 0.95
        ):
            next_fragment['warn'] = True
            continue

        if (
                silence_after and silence_after[1] - silence_after[0] > 0.1 and
                silence_after[0] - silence_between[1] < 0.5 and
                silence_between[1] - silence_between[0] < 0.95
        ):
            next_fragment['warn'] = True
            continue

    return alignment


def get_closest_fragment(target: dict, others: List[dict]):
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
    full_transcript = '\t'.join(transcript)
    full_transcript_hash = sha1(full_transcript.encode()).hexdigest()
    path_to_transcript = os.path.join(CACHE_DIR, f'{full_transcript_hash}.txt')

    with open(path_to_audio_file, 'rb') as f:
        audio_file_hash = hash_file(f)

    with open(path_to_transcript, 'w') as f:
        f.writelines('\n'.join(transcript))

    path_to_alignment_tmp = os.path.join(CACHE_DIR, f'{full_transcript_hash}_{audio_file_hash}.json')

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


def get_fragment_hash(fragment: dict, salt: str=None):
    hash_ = sha1(f"{salt or ''}{fragment['text']}".encode()).hexdigest()
    return f'{hash_}_{fragment["begin"]}_{fragment["end"]}'


def smart_cut(fragment: dict, silences: List[Tuple[float, float]], path_to_wav: str, language: str, separator: str=None, depth=0):
    if fragment['end'] - fragment['begin'] < 10 or depth > 3:
        return [fragment]
    possible_silences = [
        s for s in silences
        if s[0] > fragment['begin'] and s[1] < fragment['end'] and s[1] - s[0] > 0.3
    ]
    if not possible_silences:
        return [fragment]

    if separator is None:
        options = [
            smart_cut(
                fragment=fragment,
                silences=possible_silences,
                path_to_wav=path_to_wav,
                language=language,
                separator=sep,
                depth=depth,
            )
            for sep in ['… ', '... ', '. ', ', ']
            if sep in fragment['text']
        ]
        sorted_options = sorted(options, key=lambda x: max(f['end'] - f['begin'] for f in x))
        return sorted_options[0] if sorted_options else [fragment]

    def cleanup(text: str) -> str:
        text = re.sub(CLEANUP_REG, r'\1', text)
        return text

    words = [w for w in cleanup(fragment['text']).split(separator)]
    if len(words) == 1:
        return [fragment]

    with tempfile.NamedTemporaryFile(suffix='.wav') as file_:
        sox.trim(path_to_wav, file_.name, from_=fragment['begin'], to=fragment['end'])
        sub_alignment = build_alignment(
            transcript=words,
            path_to_audio=file_.name,
            existing_alignment=[],
            silences=[
                (s_start - fragment['begin'], s_end - fragment['begin'])
                for s_start, s_end in possible_silences
            ],
            generate_labels=True,
            language=language,
            separator=separator,
            depth=depth + 1,
        )
    if len(sub_alignment) == 1:
        return [fragment]

    options = []
    for silence_start, silence_end in possible_silences:

        left_fragments = [f for f in sub_alignment if f['begin'] < silence_start and f['end'] <= silence_end]
        right_fragments = [f for f in sub_alignment if f['begin'] >= silence_start and f['end'] > silence_end]
        if not left_fragments or not right_fragments or len(left_fragments) + len(right_fragments) != len(sub_alignment):
            continue
        left = deepcopy(fragment)
        left.update(
            text=separator.join(f['text'] for f in left_fragments),
            begin=left_fragments[0]['begin'] + fragment['begin'],
            end=left_fragments[-1]['end'] + fragment['begin'],
        )
        right = deepcopy(fragment)
        right.update(
            text=separator.join(f['text'] for f in right_fragments),
            begin=right_fragments[0]['begin'] + fragment['begin'],
            end=right_fragments[-1]['end'] + fragment['begin'],
            warn=True,
        )
        right.pop('approved', None)
        options.append(
            smart_cut(left, silences=possible_silences, path_to_wav=path_to_wav, language=language, depth=depth + 1) + \
            smart_cut(right, silences=possible_silences, path_to_wav=path_to_wav, language=language, depth=depth + 1)
        )
    if not options:
        return [fragment]
    sorted_options = sorted(options, key=lambda x: max(f['end'] - f['begin'] for f in x))
    return sorted_options[0]


def build_alignment(transcript: List[str], path_to_audio: str, existing_alignment: List[dict], silences: List[Tuple[float, float]], generate_labels=False, language='fr_FR', separator=None, depth=0):

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
                    if last_deleted_fragment_index is None:
                        alignment_transcript_mapping[f_i].append(t_i)
                    else:
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
                    language=language,
                    separator=separator,
                )
            for fragment in sub_alignment:
                fragment['begin'] = round(fragment['begin'] + group_start, 3)
                fragment['end'] = round(fragment['end'] + group_start, 3)
            alignment += sub_alignment
    else:
        existing_alignment = get_alignment(path_to_audio_file=path_to_audio, transcript=transcript, language=language)

        alignment = fix_alignment(existing_alignment, silences, separator=separator)

        if any(f['end'] - f['begin'] <= 0 for f in alignment):
            lines = ', '.join([str(i + 1) for i, f in enumerate(alignment) if f['end'] - f['begin'] <= 0])
            raise Exception(f'lines {lines} led to empty or negative alignment')

    result = []
    for i, fragment in enumerate(alignment):
        result += smart_cut(fragment, silences=silences, path_to_wav=path_to_audio, language=language, depth=depth)

    if generate_labels:
        # Generate Audacity labels for DEBUG purpose
        path_to_labels = os.path.join(CACHE_DIR, 'labels.txt')
        with open(path_to_labels, 'w') as fragment:
            fragment.writelines('\n'.join([
                f'{s}\t{e}\tsilence#{i+1:03d}'
                for i, (s, e) in enumerate(silences)
            ] + [
                f'{f["begin"]}\t{f["end"]}\tf#{i+1:03d}:{f["text"]}'
                for i, f in enumerate(result)
            ] + [
                f'{f["begin"]}\t{f["end"]}\to#{i+1:03d}:{f["text"]}'
                for i, f in enumerate(existing_alignment)
            ]) + '\n')

    return result


def transition_silences(left_fragment, right_fragment, silences):
    silences_between = [
        s
        for s in silences
        if s[0] <= left_fragment['end'] and s[1] >= right_fragment['begin']
    ]

    if len(silences_between) > 1:
        raise NotImplementedError

    silence_between = silences_between[0] if silences_between else None

    silence_before = next((
        s for s in reversed(silences)
        if (
            s[1] < (silence_between[0] if silence_between else left_fragment['end']) and
            s[0] > left_fragment['begin']
        )
    ), None)

    silence_after = next((
        s for s in silences
        if (
            s[0] > (silence_between[1] if silence_between else right_fragment['begin']) and
            s[1] < right_fragment['end']
        )
    ), None)
    return silence_before, silence_between, silence_after


def format_timedelta(td: timedelta):
    s = td.total_seconds()
    # hours
    hours = int(s // 3600)
    # remaining seconds
    s = s - (hours * 3600)
    # minutes
    minutes = int(s // 60)
    # remaining seconds
    seconds = int(s - (minutes * 60))
    milliseconds = int(round(td.microseconds / 1000, 3))
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}'


PUNCTUATIONS_REG = re.compile(r"[°\-,;!?.()\[\]*…—]")
MULTIPLE_SPACES_REG = re.compile(r'\s{2,}')


def cleanup_transcript(text: str) -> str:
    text = text.replace('’', "'")
    text = PUNCTUATIONS_REG.sub(' ', text)
    text = MULTIPLE_SPACES_REG.sub(' ', text)
    return text.strip().lower()


def merge_overlaps(silences: Iterator[Tuple[float, float]], margin=0.06001) -> Iterator[Tuple[float, float]]:
    silences = list(silences)
    current_group = None
    for silence in silences:
        if current_group is None:
            current_group = silence
            continue
        current_group_start, current_group_end = current_group
        silence_start, silence_end = silence
        assert current_group_start < current_group_end
        assert silence_start < silence_end
        if silence_start - current_group_end <= margin:
            current_group = (min(silence_start, current_group_start), max(current_group_end, silence_end))
            continue
        yield current_group
        current_group = silence

    if current_group:
        yield current_group
