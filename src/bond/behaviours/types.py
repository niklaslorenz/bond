import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel
from returns.result import Result

from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, SystemMessage, UserConversationMessage

logger = logging.getLogger(__name__)


class MessageListBuilder(Protocol):
    def __call__(
        self,
        conversation: Conversation,
        system_message: str | None,
        turns: int | None = None,
    ) -> tuple[SystemMessage | None, list[Message]]: ...


class PauseRequest:
    def __init__(self):
        self._paused: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        self._resume = asyncio.Event()

    def paused(self):
        if not self._paused.done():
            self._paused.set_result(None)

    def cancel(self):
        if not self._paused.done():
            self._paused.cancel()

    async def wait_until_paused(self):
        await self._paused

    def resume(self):
        self._resume.set()

    async def wait_until_resume(self):
        await self._resume.wait()


@dataclass
class InputSignal:
    message: UserConversationMessage


@dataclass
class ContinueSignal:
    pass


@dataclass
class StopSignal:
    pass


AsyncLoopSignal = InputSignal | PauseRequest | ContinueSignal | StopSignal


class AsyncLoopSignalBuffer:
    def __init__(self):
        self._user_input: UserConversationMessage | None = None
        self._pause_requests: list[PauseRequest] = []
        self._continue: bool = False
        self._stop: bool = False
        self._stop_immediate: bool = False

        self._waiter: asyncio.Future[AsyncLoopSignal] | None = None

    def signal_user_input(
        self, user_input: UserConversationMessage
    ) -> Result[None, str]:
        if self._user_input is not None:
            return Result.from_failure("Pending User Input")
        self._user_input = user_input
        self._check_waiter()
        return Result.from_value(None)

    def signal_continue(self):
        self._continue = True
        self._check_waiter()

    def request_pause(self, request: PauseRequest):
        self._pause_requests.append(request)
        self._check_waiter()

    def signal_stop(self, immediate: bool = False):
        self._stop = True
        if immediate:
            self._stop_immediate = True
        self._check_waiter()

    def clear(self):
        """Clear the Input Signals (Stopping signals and pause requests are kept)"""
        self._user_input = None
        self._continue = False

    async def pull(self) -> AsyncLoopSignal:
        if (signal := self._build_signal()) is not None:
            return signal
        future: asyncio.Future[AsyncLoopSignal] = (
            asyncio.get_event_loop().create_future()
        )
        if self._waiter is not None:
            raise RuntimeError("Already having a waiter")
        self._waiter = future
        try:
            return await future
        finally:
            if self._waiter is future:
                self._waiter = None

    def release(self):
        """Release all waiting tasks by raising an asyncio.CancelledError"""
        if self._waiter is not None:
            self._waiter.cancel()
        self._waiter = None
        for request in self._pause_requests:
            request.cancel()
        self._pause_requests.clear()

    def __del__(self):
        if self._waiter is not None or self._pause_requests:
            logger.warning("AsyncTurnSignalBuffer was destroyed without proper cleanup")

    def _check_waiter(self):
        if self._waiter is not None and (signal := self._build_signal()) is not None:
            waiter = self._waiter
            self._waiter = None
            waiter.set_result(signal)

    def _build_signal(self) -> AsyncLoopSignal | None:
        if self._stop_immediate:
            self.clear()
            self._stop = False
            for request in self._pause_requests:
                request.cancel()
            self._pause_requests.clear()
            return StopSignal()
        if self._pause_requests:
            request = self._pause_requests[0]
            self._pause_requests.remove(request)
            return request
        if self._stop:
            self.clear()
            self._stop = False
            return StopSignal()
        if self._user_input is not None:
            signal = InputSignal(self._user_input)
            self.clear()
            return signal
        if self._continue:
            self.clear()
            return ContinueSignal()
        return None


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
