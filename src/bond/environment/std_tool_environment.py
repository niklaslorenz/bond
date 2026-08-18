import sys
from pathlib import Path
from typing import Callable, TextIO

from . import logger


class StdToolEnvironment:
    def __init__(
        self,
        work_dir: Path | Callable[[], Path] | None,
        is_interactive: bool,
        show_tool_output: bool,
        show_tool_logs: bool,
        executing_persona: str | None,
    ):
        self.work_dir = work_dir
        self._is_interactive = is_interactive
        self.show_tool_output = show_tool_output
        self.show_logs = show_tool_logs
        self._executing_persona: str | None = executing_persona

    def executing_persona(self) -> str | None:
        return self._executing_persona

    def set_executing_persona(self, executing_persona: str | None):
        self._executing_persona = executing_persona

    def is_interactive(self) -> bool:
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

    def supports_stdout(self) -> bool:
        return True

    def stdout(self) -> TextIO | None:
        return sys.stdout

    def log_out(self) -> TextIO | None:
        if self.show_logs:
            return sys.stdout
        else:
            return None

    def log_err(self) -> TextIO | None:
        if self.show_logs:
            return sys.stderr
        else:
            return None
