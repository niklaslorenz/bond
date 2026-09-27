from abc import ABC, abstractmethod

from bond.behaviours.async_turn_event import (
    AsyncTurnAutoSummaryEvent,
    AsyncTurnErrorEvent,
    AsyncTurnFullResponseEvent,
    AsyncTurnMessageInsertedEvent,
    AsyncTurnResponseChunkEvent,
    AsyncTurnResponseEndEvent,
    AsyncTurnResponseStartEvent,
    AsyncTurnToolCallEvent,
    AsyncTurnToolReturnEvent,
)


class AsyncTurnEventHandler(ABC):
    @abstractmethod
    async def handle_auto_summary_event(self, event: AsyncTurnAutoSummaryEvent): ...
    @abstractmethod
    async def handle_error_event(self, event: AsyncTurnErrorEvent): ...
    @abstractmethod
    async def handle_full_response_event(self, event: AsyncTurnFullResponseEvent): ...
    @abstractmethod
    async def handle_message_inserted_event(
        self, event: AsyncTurnMessageInsertedEvent
    ): ...
    @abstractmethod
    async def handle_response_chunk_event(self, event: AsyncTurnResponseChunkEvent): ...
    @abstractmethod
    async def handle_response_end_event(self, event: AsyncTurnResponseEndEvent): ...
    @abstractmethod
    async def handle_response_start_event(self, event: AsyncTurnResponseStartEvent): ...
    @abstractmethod
    async def handle_tool_call_event(self, event: AsyncTurnToolCallEvent): ...
    @abstractmethod
    async def handle_tool_return_event(self, event: AsyncTurnToolReturnEvent): ...
