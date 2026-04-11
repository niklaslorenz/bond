from typing import Literal, Protocol

from pydantic import BaseModel


class BehaviourSignal(BaseModel):
    pass


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


class BehaviourSignalReceiver(Protocol):
    def get(self) -> BehaviourSignal: ...
    def peek(self) -> BehaviourSignal | None: ...
