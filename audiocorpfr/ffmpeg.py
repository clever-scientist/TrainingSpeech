import json
import os
import re
import subprocess
from typing import List, Tuple, Iterator

from audiocorpfr import sox, utils


def convert(from_: str, to: str, rate: int=None, channels: int=None, loglevel='quiet'):
    options = ' '
    if rate is not None:
        options += f'-ar {rate} '
    if channels is not None:
        options += f'-ac {channels} '
    if loglevel:
        options += f'-loglevel {loglevel} '
    retcode = subprocess.call(f'ffmpeg -y -i {from_}{options}{to}'.split(' '))
    assert retcode == 0


def cut(input_path: str, output_path: str, from_: float=None, to: float=None, loglevel='quiet'):
    assert os.path.abspath(input_path) != os.path.abspath(output_path)
    if from_ is not None and to is not None:
        # NB: use sox.trim since ffmpeg do not perform very well...
        return sox.trim(input_path, output_path, from_, to)

    options = ' '
    if from_ is not None:
        options += f'-ss {from_} '
    if to is not None:
        options += f'-to {to} '
    if loglevel:
        options += f'-loglevel {loglevel} '
    subprocess.call(f'ffmpeg -y -i {input_path}{options}-c copy {output_path}'.split(' '))


SILENCE_END_DUR_REG = re.compile(r'^.*?silence_end:\s*(-?\d+\.?\d*)\s*\|\s*silence_duration:\s*(-?\d+\.?\d*)$')
SILENCE_START_REG = re.compile(r'^.*?silence_start:\s*(-?\d+\.?\d*)\s*$')


def audio_duration(input_path: str) -> float:
    assert os.path.isfile(input_path)
    input_path = os.path.abspath(input_path)

    duration = subprocess.check_output([
        'ffprobe', '-i', input_path,
        '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=%s' % "p=0"
    ])

    return float(duration)


def list_silences(input_path: str, noise_level: int=-50, min_duration: float=0.05, force=False) -> List[Tuple[float, float]]:
    with open(input_path, 'rb') as f:
        audio_hash = utils.hash_file(f)

    from audiocorpfr.utils import file_extension
    if file_extension(input_path) == '.mp3':
        path_to_wav = f'/tmp/{audio_hash}.wav'
        convert(input_path, path_to_wav)
        input_path = path_to_wav

    cached_path = f'/tmp/{audio_hash}_{noise_level}_{min_duration}.json'
    if not force and os.path.isfile(cached_path):
        with open(cached_path) as f:
            return json.load(f)

    p = subprocess.Popen(
        f'ffmpeg -i {input_path} -af silencedetect=noise={noise_level}dB:d={min_duration} -f null -'.split(' '),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    def parse_lines(lines: List[bytes]) -> Iterator[Tuple[float, float]]:
        first_silence_start = None
        last_silence_start = None
        for line_b in lines:
            line_s = line_b.decode().strip()
            match_start = SILENCE_START_REG.match(line_s)

            if match_start:
                silence_start = float(match_start.group(1))
                if first_silence_start is None:
                    first_silence_start = min(silence_start, 0)
                last_silence_start = silence_start
            match_end_dur = SILENCE_END_DUR_REG.match(line_s)
            if match_end_dur:
                silence_end, silence_duration = match_end_dur.groups()
                silence_end, silence_duration = float(silence_end), float(silence_duration)
                yield round(silence_end - silence_duration - first_silence_start, 3), round(silence_end - first_silence_start, 3)
        if last_silence_start:
            yield round(last_silence_start, 3), round(audio_duration(input_path), 3)

    def merge_overlaps(silences: Iterator[Tuple[float, float]]) -> Iterator[Tuple[float, float]]:
        current_group = None
        for silence in silences:
            if current_group is None:
                current_group = silence
                continue
            current_group_start, current_group_end = current_group
            silence_start, silence_end = silence
            assert current_group_start < current_group_end
            assert silence_start < silence_end
            # assert silence_start >= current_group_start, f'{silence_start} not gte {current_group_start}'
            if silence_start - current_group_end <= 0.05:
                current_group = min(silence_start, current_group_start), max(current_group_end, silence_end)
                continue
            yield current_group
            current_group = silence

        if current_group:
            yield current_group

    result = [[round(s, 3), round(e, 3)] for s, e in merge_overlaps(parse_lines(p.stderr.readlines()))]
    with open(cached_path, 'w') as f:
        json.dump(result, f)
    return result
