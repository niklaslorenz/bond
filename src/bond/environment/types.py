from typing import Protocol

from bond.behaviours.behaviour_signal import BehaviourSignal


class IBehaviourSignalHandler(Protocol):
    def queue_signal(self, signal: BehaviourSignal): ...
