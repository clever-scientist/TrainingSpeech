class GoBackException(Exception):
    pass


class QuitException(Exception):
    pass


class MergeException(Exception):
    pass


class WrongCutException(Exception):
    pass


class RebuildRequiredException(Exception):
    def __init__(self, n):
        self.n = n
