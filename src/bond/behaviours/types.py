from typing import Protocol

from pydantic import BaseModel


class BehaviourEvent(BaseModel):
    type: str


class BehaviourSignal(BaseModel):
    type: str


class IBehaviourEventHandler(Protocol):
    def __call__(self, event: BehaviourEvent) -> None: ...


class IBehaviourSignalReceiver(Protocol):
    def get(self) -> BehaviourSignal: ...
    def peek(self) -> BehaviourSignal | None: ...
