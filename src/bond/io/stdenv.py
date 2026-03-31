import sys
from pathlib import Path
from typing import Callable

from bond.behaviours.behaviour_signal import (
    BehaviourSignal,
    CommandSignal,
    PromptSignal,
)
from bond.io.stream import WritethroughWrapper
from bond.io.string_io import StringAoe

from . import logger


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


class StdIoToolEnvironment:
    def __init__(
        self, work_dir: Path | Callable[[], Path] | None, is_interactive: bool
    ):
        self.work_dir = work_dir
        self._is_interactive = is_interactive
        pass

    def is_interactive(self):
        return self._is_interactive

    def ask_confirmation(self, prompt: str) -> bool:
        if not self.is_interactive():
            return False
        print(prompt)
        try:
            while True:
                access = input("[yes|no] > ")
                if access == "yes" or access == "y":
                    return True
                if access == "no" or access == "n":
                    return False
                print("Invalid input.")
        except Exception as e:
            logger.error(e)
            return False

    def get_work_dir(self) -> Path | None:
        if self.work_dir is None:
            return None
        if isinstance(self.work_dir, Path):
            return self.work_dir
        return self.work_dir()
