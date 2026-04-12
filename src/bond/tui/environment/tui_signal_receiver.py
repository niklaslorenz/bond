from multiprocessing import Queue
from queue import Empty

from bond.behaviours.behaviour_signal import BehaviourSignal


class TuiSignalReceiver:
    def __init__(self, queue: Queue):
        self._queue = queue
        self._head = None

    def peek(self) -> BehaviourSignal | None:
        if self._head is not None:
            return self._head
        try:
            self._head = self._queue.get_nowait()
        except Empty:
            self._head = None
        return self._head

    def get(self) -> BehaviourSignal:
        if self._head is not None:
            val = self._head
            self._head = None
            return val
        return self._queue.get()
