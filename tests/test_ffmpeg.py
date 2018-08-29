import pytest
from audiocorpfr import ffmpeg


@pytest.mark.parametrize('kwargs, expected_call', [
    (dict(from_='foo.mp3', to='foo.wav'), 'ffmpeg -y -i foo.mp3 -loglevel quiet foo.wav'),
    (dict(from_='foo.mp3', to='foo.wav', rate=16000, channels=1), 'ffmpeg -y -i foo.mp3 -ar 16000 -ac 1 -loglevel quiet foo.wav'),
])
def test_convert(kwargs, expected_call, mocker):
    call_mock = mocker.patch('subprocess.call', return_value=0)
    ffmpeg.convert(**kwargs)
    call_mock.assert_called_once_with(expected_call.split(' '))
