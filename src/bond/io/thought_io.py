from typing import TextIO


class ThoughtIO(TextIO):
    def __init__(self, wrapped: TextIO):
        self._stream = wrapped

    def write(self, s: str):
        s = self._prefix + s + self._suffix
        return self._stream.write(s)

    def writelines(self, lines: list[str]):
        if not lines:
            return 0

        modified_lines = lines.copy()
        modified_lines[0] = "<think>" + modified_lines[0]
        modified_lines[-1] = "</think>" + modified_lines[-1]
        return self._stream.writelines(modified_lines)

    def __getattr__(self, name):
        return getattr(self._stream, name)
