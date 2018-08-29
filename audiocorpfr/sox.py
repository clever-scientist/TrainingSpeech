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
