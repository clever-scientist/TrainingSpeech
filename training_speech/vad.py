import json
import os
import wave
from itertools import zip_longest

import webrtcvad

from training_speech import ffmpeg, utils


def list_silences(path_to_wav: str, force: bool = False, mode=utils.DEFAULT_VAD_MODE, frame_duration=utils.DEFAULT_VAD_FRAME_DURATION, merge=True):
    with open(path_to_wav, 'rb') as f:
        audio_hash = utils.hash_file(f)

    cached_path = os.path.join(utils.CACHE_DIR, f'wav_{audio_hash}_{mode}_{frame_duration}.json')
    if not force and os.path.isfile(cached_path):
        with open(cached_path) as f:
            return json.load(f)

    duration_sec = ffmpeg.audio_duration(path_to_wav)
    vad_ = webrtcvad.Vad(mode=mode)

    def _read_wav(translate=False):
        with wave.open(path_to_wav) as wave_f:
            nchannels, sampwidth, framerate, nframes, comptype, compname = wave_f.getparams()
            assert nchannels == 1
            assert sampwidth == 2  # 2bytes = 16bits
            assert framerate in {8000, 16000, 32000, 48000}, f'{framerate} not in [8000, 16000, 32000, 48000]'
            assert frame_duration in {10, 20, 30}, f'{framerate} not in [10,20,30]'
            vad_frame_len = int(framerate * frame_duration / 1000)
            if translate:
                half = int(vad_frame_len / 2)
                wave_f.readframes(half)
                nframes -= half

            for _ in range(int(nframes / vad_frame_len)):
                frame = wave_f.readframes(vad_frame_len)
                try:
                    yield vad_.is_speech(frame, framerate)
                except Exception as e:
                    print(e, path_to_wav)
                    yield False

    silences = []
    current_speech = None
    left = list(_read_wav())
    middle = _read_wav(translate=True)
    half_frame_dur = frame_duration / 2 / 1000.
    is_speech_decision_tree = {
        # Left, Middle, Right
        (False, False, False): (False, 0, 0),
        (False, False, True): (False, 0, half_frame_dur),
        (False, False, None): (False, 0, half_frame_dur),
        (False, True, False): (False, 0, 0),  # assume false-positive
        (False, True, True): (True, 0, 0),  # preserve previous silence
        (False, True, None): (False, 0, half_frame_dur),
        (False, None, None): (False, 0, 2 * half_frame_dur),
        (True, False, False): (False, half_frame_dur, 0),
        (True, False, True): (True, 0, 0),
        (True, False, None): (False, 0, half_frame_dur),
        (True, True, False): (True, 0, half_frame_dur),
        (True, True, True): (True, 0, 0),
        (True, True, None): (True, 0, half_frame_dur),
        (True, None, None): (True, 0, 2 * half_frame_dur),
    }

    for i, (left_is_speech, right_is_speech, middle_is_speech) in enumerate(zip_longest(left, left[1:], middle)):
        is_speech, start_delta, end_delta = \
            is_speech_decision_tree[(left_is_speech, middle_is_speech, right_is_speech)]

        start = i * frame_duration / 1000. + start_delta
        end = (i + 2) * frame_duration / 1000. - end_delta

        if current_speech is None and not is_speech:
            current_speech = (start, None)

        if current_speech and is_speech:
            silences.append(current_speech)
            current_speech = None
            continue

        if current_speech and not is_speech:
            current_speech = (current_speech[0], end)

    if current_speech:
        silences.append(current_speech)

    if silences and ((duration_sec - silences[-1][1]) < frame_duration / 2 or silences[-1][1] is None):
        silences[-1] = (silences[-1][0], duration_sec)

    silences = [
        (round(s, 3), round(e, 3))
        for s, e in (utils.merge_overlaps(silences, margin=0.07001) if merge else silences)
        if e - s > 0.0401
    ]
    with open(cached_path, 'w') as f:
        json.dump(silences, f)

    return silences
