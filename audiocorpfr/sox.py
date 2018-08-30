import subprocess
from contextlib import contextmanager


@contextmanager
def play(path_to_file: str, speed: float=None):
    options = ''
    if speed is not None:
        options += f'tempo {speed}'
    player = subprocess.Popen(f'play -q {path_to_file} {options}'.strip().split(' '))
    yield player
    player.wait()


def trim(input_path: str, output_path: str, from_: float, to: float):
    assert to > from_
    duration = round(to - from_, 4)
    subprocess.call(f'sox {input_path.strip()} {output_path.strip()} trim {from_} {duration}'.split(' '))
