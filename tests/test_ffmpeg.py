import os

import pytest
from audiocorpfr import ffmpeg

CURRENT_DIR = os.path.dirname(__file__)


@pytest.mark.parametrize('kwargs, expected_call', [
    (dict(from_='foo.mp3', to='foo.wav'), 'ffmpeg -y -i foo.mp3 -loglevel quiet foo.wav'),
    (dict(from_='foo.mp3', to='foo.wav', rate=16000, channels=1), 'ffmpeg -y -i foo.mp3 -ar 16000 -ac 1 -loglevel quiet foo.wav'),
])
def test_convert(kwargs, expected_call, mocker):
    call_mock = mocker.patch('subprocess.call', return_value=0)
    ffmpeg.convert(**kwargs)
    assert call_mock.call_count == 1
    call_args, call_kwargs = call_mock.call_args
    assert ' '.join(call_args[0]) == expected_call


@pytest.mark.parametrize('kwargs, expected_call', [
    (
            dict(input_path='input.wav', output_path='output.wav', from_=1, to=10),
            'ffmpeg -y -i input.wav -ss 1 -to 10 -loglevel quiet -c copy output.wav',
    ),
    (
            dict(input_path='input.wav', output_path='output.wav', from_=1),
            'ffmpeg -y -i input.wav -ss 1 -loglevel quiet -c copy output.wav',
    ),
    (
            dict(input_path='input.wav', output_path='output.wav', to=10),
            'ffmpeg -y -i input.wav -to 10 -loglevel quiet -c copy output.wav',
    ),
])
def test_cut(kwargs, expected_call, mocker):
    call_mock = mocker.patch('subprocess.call', return_value=0)
    ffmpeg.cut(**kwargs)
    assert call_mock.call_count == 1
    call_args, call_kwargs = call_mock.call_args
    assert ' '.join(call_args[0]) == expected_call


def test_list_silences():
    path_to_wav = os.path.join(CURRENT_DIR, './assets/test.wav')
    silences = ffmpeg.list_silences(path_to_wav)
    with open('/tmp/labels.txt', 'w') as f:
        f.writelines('\n'.join([f'{s}\t{e}\tsilence{i+1}' for i, (s, e) in enumerate(silences)]) + '\n')
    assert silences == [
        (0, 0.178),
        (1.024, 1.458),
        (2.048, 2.61),
        (3.072, 4.864),
    ]


def test_audio_duration():
    path_to_wav = os.path.join(CURRENT_DIR, './assets/test.wav')
    assert ffmpeg.audio_duration(path_to_wav) == 4.864
