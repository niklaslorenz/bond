import asyncio
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel
from returns.result import Result

from bond.capabilities.generation import GenerationTriggers
from bond.conversation.types import ToolConversationMessage, UserConversationMessage

logger = logging.getLogger(__name__)

TurnStatus = Literal["Receiving", "Summarizing", "Stopped"]

LoopStatus = Literal[
    "Waiting", "Idle", "Tool Call", "Receiving", "Paused", "Stopped", "Summarizing"
]


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
class StopSignal:
    pass


AsyncLoopSignal = GenerationTriggers | PauseRequest | StopSignal


class AsyncLoopSignalBuffer:
    def __init__(self):
        self._user_input: UserConversationMessage | None = None
        self._tool_outputs: list[ToolConversationMessage] | None = None

        self._pause_requests: list[PauseRequest] = []
        self._stop: bool = False
        self._stop_immediate: bool = False
        self._interrupt: bool = False

        self._waiter: asyncio.Future[AsyncLoopSignal] | None = None

    def has_waiter(self) -> bool:
        return self._waiter is not None

    def signal_user_input(
        self, user_input: UserConversationMessage
    ) -> Result[None, str]:
        if self._user_input is not None:
            return Result.from_failure("Pending User Input")
        self._user_input = user_input
        self._interrupt = False
        self._check_waiter()
        return Result.from_value(None)

    def signal_tool_outputs(
        self, tool_outputs: list[ToolConversationMessage]
    ) -> Result[None, str]:
        if self._tool_outputs is not None:
            return Result.from_failure("Pending Tool Outputs")
        self._tool_outputs = tool_outputs
        self._check_waiter()
        return Result.from_value(None)

    def request_pause(self, request: PauseRequest):
        self._pause_requests.append(request)
        self._check_waiter()

    def signal_stop(self, immediate: bool = False):
        self._stop = True
        if immediate:
            self._stop_immediate = True
        self._check_waiter()

    def interrupt(self):
        """Interrupt the loop and not continue on tool outputs"""
        self._interrupt = True

    def resume(self):
        """Resume the loop and continue relaying tool outputs"""
        if self._interrupt:
            self._interrupt = False
            self._check_waiter()

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
            self._clear()
            self._stop = False
            self._stop_immediate = False
            for request in self._pause_requests:
                request.cancel()
            self._pause_requests.clear()
            return StopSignal()
        if self._pause_requests:
            request = self._pause_requests[0]
            self._pause_requests.remove(request)
            return request
        if self._stop:
            self._clear()
            self._stop = False
            return StopSignal()
        if self._user_input is not None or (
            self._tool_outputs is not None and not self._interrupt
        ):
            signal = GenerationTriggers(self._user_input, self._tool_outputs)
            self._clear()
            return signal
        return None

    def _clear(self):
        """Clear the Input Signals (Stopping signals and pause requests are kept)"""
        self._user_input = None
        self._tool_outputs = None
        self._interrupt = False
