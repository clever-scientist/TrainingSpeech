import os
import pytest

from training_speech import vad

CURRENT_DIR = os.path.dirname(__file__)


@pytest.mark.parametrize('input_file, mode, frame_duration, expected_silences', [
    ('test.wav', 3, 30, [(0.0, 0.18), (1.11, 1.44), (2.145, 2.58), (3.12, 4.864)]),
    ('silence.wav', 3, 20, [(0.0, 1.108)]),
])
def test_list_silences(input_file, mode, frame_duration, expected_silences):
    path_to_wav = os.path.join(CURRENT_DIR, f'./assets/{input_file}')
    silences = vad.list_silences(path_to_wav, mode=mode, frame_duration=frame_duration, force=True)
    assert expected_silences == silences
