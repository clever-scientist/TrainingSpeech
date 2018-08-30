import os
import re
import subprocess
from typing import List, Tuple, Iterator

from audiocorpfr import sox


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


def list_silences(input_path: str, noise_level: int=-50, min_duration: float=0.05) -> List[Tuple[float, float]]:
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
                yield silence_end - silence_duration - first_silence_start, silence_end - first_silence_start
        if last_silence_start:
            yield last_silence_start, audio_duration(input_path)

    def merge_overlaps(silences: Iterator[Tuple[float, float]]) -> Iterator[Tuple[float, float]]:
        current_group = None
        for item in silences:
            if current_group is None:
                current_group = item
                continue
            cg_s, cg_e = current_group
            i_s, i_e = item
            assert cg_s < cg_e
            assert i_s < i_e
            assert i_s >= cg_s, f'{i_s} not gte {cg_s}'
            if i_s - cg_e <= 0.05:
                current_group = cg_s, max(cg_e, i_e)
                continue
            yield current_group
            current_group = item

        if current_group:
            yield current_group

    result = [(round(s, 3), round(e, 3)) for s, e in merge_overlaps(parse_lines(p.stderr.readlines()))]
    # result = [(round(s, 3), round(e, 3)) for s, e in parse_lines(p.stderr.readlines())]
    return result
