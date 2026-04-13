from typing import Literal

from bond.behaviours.types import BehaviourSignal


class StopSignal(BehaviourSignal):
    """
    Event for stopping the loop behaviour
    To interrupt during a turn, use the InterruptSignal.
    """

    type: Literal["stop"] = "stop"


class PromptSignal(BehaviourSignal):
    type: Literal["prompt"] = "prompt"
    prompt: str


class CommandSignal(BehaviourSignal):
    type: Literal["command"] = "command"
    command: str


class InterruptSignal(BehaviourSignal):
    """
    Event to interrupt a single turn.
    To stop the loop behaviour inbetween turns, use the StopSignal
    """

    type: Literal["interrupt"] = "interrupt"
