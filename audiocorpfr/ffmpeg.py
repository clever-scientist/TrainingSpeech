import subprocess


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
