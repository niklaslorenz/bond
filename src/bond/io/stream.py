from typing import TextIO


class WritethroughWrapper(TextIO):
    def __init__(self, wrapped: TextIO):
        self._wrapped = wrapped

    def write(self, s: str, /) -> int:
        x = self._wrapped.write(s)
        self._wrapped.flush()
        return x

    def writelines(self, lines: list[str], /) -> None:
        self._wrapped.writelines(lines)
        self._wrapped.flush()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


class ThoughtWrapper(TextIO):
    def __init__(
        self, wrapped: TextIO, prefix: str = "\n<think>\n", suffix: str = "\n</think>\n"
    ):
        self._wrapped = wrapped
        self._prefix = prefix
        self._suffix = suffix

    def write(self, s: str, /) -> int:
        if s != "":
            s = self._prefix + s + self._suffix
        return self._wrapped.write(s)

    def writelines(self, lines: list[str], /) -> None:
        if not lines:
            return
        modified_lines = lines.copy()
        modified_lines[0] = "<think>" + modified_lines[0]
        modified_lines[-1] = "</think>" + modified_lines[-1]
        return self._wrapped.writelines(modified_lines)

    def __getattr__(self, name):
        return getattr(self._wrapped, name)
