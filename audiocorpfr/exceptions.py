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
    pass
