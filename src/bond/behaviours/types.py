import asyncio
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, SystemMessage, UserConversationMessage


class MessageListBuilder(Protocol):
    def __call__(
        self,
        conversation: Conversation,
        system_message: str | None,
        turns: int | None = None,
    ) -> tuple[SystemMessage | None, list[Message]]: ...


@dataclass
class InputTrigger:
    message: UserConversationMessage


@dataclass
class ContinueTrigger:
    reason: str | None


@dataclass
class StopTrigger:
    reason: str | None


LoopTrigger = InputTrigger | ContinueTrigger | StopTrigger


class TriggerManager:
    def __init__(self):
        self._triggers: list[LoopTrigger] = []
        self._future: asyncio.Future | None = None

    def pop(self) -> asyncio.Future[LoopTrigger]:
        if self._trigger is not None:
            trigger = self._trigger
            self._trigger = None
            return trigger
        future = asyncio.get_event_loop.create_future()
        self.future = future
        return future

    def push(
        self,
        trigger: LoopTrigger,
        *,
        cancel_previous: bool = False,
        insert_when_not_empty: bool = True,
        prepend: bool = False,
    ):
        if self._triggers and not insert_when_not_empty:
            return
        if self._future is not None:
            self._future.set_result(trigger)
            self._future = None
            self._triggers.clear()
            return
        if cancel_previous:
            self._triggers.clear()
        if prepend:
            self._triggers = [trigger] + self._triggers
        else:
            self._triggers.append(trigger)

    def clear(self):
        self._triggers.clear()
        if self._future is not None:
            self._future.set_exception(asyncio.CancelledError())
        self._future = None


# TODO: clean up old syncronous event types


class BehaviourEvent(BaseModel):
    type: str


class BehaviourSignal(BaseModel):
    type: str


class IBehaviourEventHandler(Protocol):
    def __call__(self, event: BehaviourEvent) -> None: ...


class IBehaviourSignalReceiver(Protocol):
    def get(self) -> BehaviourSignal: ...
    def peek(self) -> BehaviourSignal | None: ...
