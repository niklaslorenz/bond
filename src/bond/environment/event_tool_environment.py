from concurrent.futures import CancelledError, Future
from multiprocessing import Queue
from pathlib import Path
from typing import Callable, TextIO

from bond.behaviours.behaviour_event import (BehaviourEvent,
                                             RequestConfirmationEvent,
                                             ToolReturnEvent)
from bond.conversation.types import ToolCall

_CONFIRMATION_TIMEOUT = 30


class EventToolEnvironment:
    """
    A tool environment that makes use of the event queue.
    Does not support operations for data streaming by tools.
    """

    def __init__(
        self,
        work_dir: Path | Callable[[], Path] | None,
        event_queue: Queue[BehaviourEvent],
    ):
        self._work_dir = work_dir
        self._event_queue = event_queue

    def ask_confirmation(self, prompt: str) -> bool:
        future: Future[bool] = Future()
        request = RequestConfirmationEvent(request=prompt, result=future)
        self._event_queue.put(request)
        try:
            return future.result(timeout=_CONFIRMATION_TIMEOUT)
        except CancelledError | TimeoutError:
            return False

    def is_interactive(self) -> bool:
        return True

    def get_work_dir(self) -> Path | None:
        if self._work_dir is None:
            return None
        if isinstance(self._work_dir, Path):
            return self._work_dir
        return self._work_dir()

    # INFO: Methods for weird streaming tools

    def supports_stdout(self) -> bool:
        return False

    def stdout(self) -> TextIO | None:
        pass

    def log_out(self) -> TextIO | None:
        return None

    def log_err(self) -> TextIO | None:
        return None
