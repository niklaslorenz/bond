import sys
from typing import Callable

from bond.behaviours.behaviour_signal import (BehaviourSignal, CommandSignal,
                                              PromptSignal)
from bond.io.stream import WritethroughWrapper
from bond.io.string_io import StringAoe


class StdAoe(StringAoe):
    def __init__(self):
        super().__init__(WritethroughWrapper(sys.stdout), None)


class StdSignalReceiver:
    def __init__(self, persona_query: Callable[[], str] | None):
        self._get_persona = persona_query

    def set_query(self, persona_query: Callable[[], str] | None):
        self._get_persona = persona_query

    def __call__(self) -> BehaviourSignal:
        raw = input(
            f"[to {self._get_persona() if self._get_persona is not None else 'Assistant'}]> "
        )
        stripped = raw.strip()
        if stripped.startswith(":"):
            return CommandSignal(command=stripped[1:])
        return PromptSignal(prompt=raw)


class StdNotifier:
    def __call__(self, message: str):
        print(message)
