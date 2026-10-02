import asyncio
from typing import TYPE_CHECKING

from bond.behaviours.async_turn_event import *
from bond.behaviours.async_turn_event_handler import AsyncTurnEventHandler
from bond.conversation.types import TextChunk, ThinkChunk
from bond.tui.widgets.chat_log import ChatMessage

from . import logger

if TYPE_CHECKING:
    from bond.tui.app import BondTui


class TuiEventHandler(AsyncTurnEventHandler):
    def __init__(self, event_queue: asyncio.Queue[AsyncTurnEvent]):
        self._app: "BondTui | None" = None
        self._event_queue = event_queue
        self._task: asyncio.Task | None = None

    def link(self, app: "BondTui"):
        assert self._app is None, "Already initialized"
        self._app = app

    def _get_app(self) -> "BondTui":
        assert self._app is not None, "Not initialized"
        return self._app

    def is_running(self) -> bool:
        return self._task is not None

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        if self._task is not None:
            raise RuntimeError("Already running")
        if loop is None:
            loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())

    def stop_nowait(self):
        if self._task is None:
            raise RuntimeError("Not running")
        self._task.cancel()

    async def stop(self):
        if self._task is None:
            raise RuntimeError("Not running")
        task = self._task
        task.cancel()
        await task

    async def _run(self):
        try:
            while True:
                try:
                    event = await self._event_queue.get()
                    logger.debug(f"Handling Event: {type(event)}")
                    await event.dispatch(self)
                except Exception:
                    logger.exception(
                        f"Event Handler caught Exception while processing {type(event)}"
                    )
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def handle_auto_summary_event(self, event: AsyncTurnAutoSummaryEvent):
        self._get_app().chat_view.status_bar.set_status(
            "Summarizing" if not event.finished else "Waiting"
        )

    async def handle_error_event(self, event: AsyncTurnErrorEvent):
        # TODO: Show error popup instead
        self._get_app().notify(event.reason, severity="error")

    async def handle_full_response_event(self, event: AsyncTurnFullResponseEvent):
        self._get_app().chat_view.add_conversation_message(event.message)
        self._get_app().chat_view.chat_log.scroll_end()

    async def handle_message_inserted_event(self, event: AsyncTurnMessageInsertedEvent):
        logger.debug(
            f"Inserted message for {event.message.author} ({event.message.message.role})"
        )
        self._get_app().chat_view.add_conversation_message(event.message)
        self._get_app().chat_view.chat_log.scroll_end()

    async def handle_request_confirmation_event(
        self, event: AsyncTurnRequestConfirmationEvent
    ):
        logger.debug("Requesting confirmation")
        result = False
        try:
            result = await self._get_app().ask_confirmation(event.request)
        finally:
            event.result.set_result(result)

    async def handle_response_chunk_event(self, event: AsyncTurnResponseChunkEvent):
        logger.debug("Handling response chunk event")
        msg = self._get_app().chat_view.last_message
        if msg is None:
            msg = ChatMessage(author="<unknown>", role="assistant")
            self._get_app().chat_view.chat_log.add_message(msg)
        logger.debug("Appending Response Chunk Content")
        for chunk in event.chunk.choices[0].delta.content or []:
            if isinstance(chunk, TextChunk):
                logger.debug(f"Text: {chunk.text}")
                msg.append_text(chunk.text)
            if isinstance(chunk, ThinkChunk):
                text = "".join(
                    c.text for c in chunk.thinking if isinstance(c, TextChunk)
                )
                logger.debug(f"Thinking: {text}")
                msg.append_thinking(text)
        self._get_app().chat_view.chat_log.scroll_end()

    async def handle_response_end_event(self, event: AsyncTurnResponseEndEvent):
        self._get_app().chat_view.status_bar.set_status("Waiting")
        self._get_app().chat_view.status_bar.set_usage(event.usage.total_tokens)

    async def handle_response_start_event(self, event: AsyncTurnResponseStartEvent):
        self._get_app().chat_view.ensure_current_author(event.role, event.author)
        self._get_app().chat_view.status_bar.set_status("Receiving")

    async def handle_tool_call_event(self, event: AsyncTurnToolCallEvent):
        self._get_app().chat_view.status_bar.set_status("Tool Call")

    async def handle_tool_return_event(self, event: AsyncTurnToolReturnEvent):
        self._get_app().chat_view.add_conversation_message(event.result)
        self._get_app().chat_view.chat_log.scroll_end()
        self._get_app().chat_view.status_bar.set_status("Waiting")
