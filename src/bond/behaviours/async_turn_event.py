from abc import ABC, abstractmethod
from asyncio import Future
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from bond.conversation.conversation import ConversationMessage
from bond.conversation.types import ToolCall, UsageInfo
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse

if TYPE_CHECKING:
    from bond.behaviours.async_turn_event_handler import AsyncTurnEventHandler


class AsyncTurnEvent(ABC):
    @abstractmethod
    async def dispatch(self, event_handler: "AsyncTurnEventHandler"): ...


@dataclass
class AsyncTurnAutoSummaryEvent(AsyncTurnEvent):
    finished: bool

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_auto_summary_event(self)


@dataclass
class AsyncTurnErrorEvent(AsyncTurnEvent):
    reason: str

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_error_event(self)


@dataclass
class AsyncTurnFullResponseEvent(AsyncTurnEvent):
    message: ConversationMessage
    response: CompletionResponse

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_full_response_event(self)


@dataclass
class AsyncTurnMessageInsertedEvent(AsyncTurnEvent):
    message: ConversationMessage

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_message_inserted_event(self)


@dataclass
class AsyncTurnResponseChunkEvent(AsyncTurnEvent):
    chunk: CompletionChunk

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_response_chunk_event(self)


@dataclass
class AsyncTurnResponseEndEvent(AsyncTurnEvent):
    usage: UsageInfo

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_response_end_event(self)


@dataclass
class AsyncTurnRequestConfirmationEvent(AsyncTurnEvent):
    request: str
    result: Future[bool]

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_request_confirmation_event(self)


@dataclass
class AsyncTurnResponseStartEvent(AsyncTurnEvent):
    author: str
    role: Literal["assistant", "user", "system"]

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_response_start_event(self)


@dataclass
class AsyncTurnToolCallEvent(AsyncTurnEvent):
    tool_call: ToolCall

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_tool_call_event(self)


@dataclass
class AsyncTurnToolReturnEvent(AsyncTurnEvent):
    result: ConversationMessage

    async def dispatch(self, event_handler: "AsyncTurnEventHandler"):
        await event_handler.handle_tool_return_event(self)
