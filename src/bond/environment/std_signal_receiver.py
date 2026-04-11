from typing import Callable

from bond.behaviours.behaviour_signal import (
    BehaviourSignal,
    CommandSignal,
    InterruptSignal,
    PromptSignal,
    StopSignal,
)


class StdSignalReceiver:
    def __init__(self):
        self._queued: list[BehaviourSignal] = []

    def peek(self) -> BehaviourSignal | None:
        if len(self._queued) > 0:
            return self._queued[0]
        return None

    def get(self) -> BehaviourSignal:
        if len(self._queued) > 0:
            return self._queued.pop(0)
        inp = input(f"[to {self.persona_query()}] ")
        if inp.startswith(":"):
            return CommandSignal(command=inp[1:])
        else:
            return PromptSignal(prompt=inp)

    def stop(self):
        self._queued.append(StopSignal())

    def interrupt(self):
        self._queued.append(InterruptSignal())

    def link(self, persona_query: Callable[[], str]):
        self.persona_query = persona_query
