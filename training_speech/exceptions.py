from typing import List


class GoBackException(Exception):
    pass


class QuitException(Exception):
    pass


class MergeException(Exception):
    def __init__(self, left, right):
        self.left = left
        self.right = right


class WrongCutException(Exception):
    pass


class SplitException(Exception):
    def __init__(self, start: int, end: int, new_transcript: List[str]):
        self.start = start
        self.end = end
        self.new_transcript = new_transcript


class ToggleFastModeException(Exception):
    pass
