from typing import TextIO


class WritethroughWrapper(TextIO):
    def __init__(self, wrapped: TextIO):
        self._wrapped = wrapped

    def write(self, s: str, /):
        self._wrapped.write(s)
        self._wrapped.flush()
        pass

    def writelines(self, lines: list[str], /):
        self._wrapped.writelines(lines)
        self._wrapped.flush()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


class ThoughtWrapper(TextIO):
    def __init__(self, wrapped: TextIO):
        self._wrapped = wrapped

    def write(self, s: str):
        s = self._prefix + s + self._suffix
        return self._wrapped.write(s)

    def writelines(self, lines: list[str]):
        if not lines:
            return 0
        modified_lines = lines.copy()
        modified_lines[0] = "<think>" + modified_lines[0]
        modified_lines[-1] = "</think>" + modified_lines[-1]
        return self._wrapped.writelines(modified_lines)

    def __getattr__(self, name):
        return getattr(self._wrapped, name)
