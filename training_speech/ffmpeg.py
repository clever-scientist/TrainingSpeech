import json
import os
import re
import subprocess
from typing import List, Tuple, Iterator

from training_speech import sox, utils


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
    assert os.path.isfile(input_path), f'no such file {input_path}'
    input_path = os.path.abspath(input_path)

    duration = subprocess.check_output([
        'ffprobe', '-i', input_path,
        '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=%s' % "p=0"
    ])

    return float(duration)


def list_silences(input_path: str, noise_level: int=-50, min_duration: float=0.05, force=False, merge=True) -> List[Tuple[float, float]]:
    with open(input_path, 'rb') as f:
        audio_hash = utils.hash_file(f)


    if utils.file_extension(input_path) == '.mp3':
        path_to_wav = os.path.join(utils.CACHE_DIR, f'{audio_hash}.wav')
        convert(input_path, path_to_wav)
        input_path = path_to_wav

    cached_path = os.path.join(utils.CACHE_DIR, f'silences_{audio_hash}_{noise_level}_{min_duration}.json')
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

    original = list(parse_lines(p.stderr.readlines()))

    result = [
        (round(s, 3), round(e, 3))
        for s, e in (utils.merge_overlaps(original) if merge else original)
    ]
    with open(cached_path, 'w') as f:
        json.dump(result, f)

    return result
