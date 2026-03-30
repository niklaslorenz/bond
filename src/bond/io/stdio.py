import sys

from bond.io.stream import WritethroughWrapper
from bond.io.string_io import StringAoe


class StdUserIO:
    def read(self, prompt: str | None = None) -> str:
        return input(prompt)

    def print(self, msg: str):
        print(msg)

    def write(self, msg: str):
        print(msg, end=None)


def StdAoe() -> StringAoe:
    return StringAoe(WritethroughWrapper(sys.stdout), None)
