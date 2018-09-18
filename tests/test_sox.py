import subprocess

import pytest

from training_speech import sox


@pytest.mark.parametrize('kwargs, expected_call', [
    (dict(path_to_file='/path/to/foo.mp3'), 'play -q /path/to/foo.mp3'),
    (dict(path_to_file='/path/to/foo.mp3', speed=1.2), 'play -q /path/to/foo.mp3 tempo 1.2'),
])
def test_convert(kwargs, expected_call, mocker):
    wait_mock = mocker.patch('subprocess.Popen.wait')
    with sox.play(**kwargs) as player:
        assert isinstance(player, subprocess.Popen)
        assert wait_mock.call_count == 0
        assert ' '.join(player.args) == expected_call
    wait_mock.assert_called_once()
