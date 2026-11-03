import asyncio
import sys

from bond.behaviours.async_turn_event import (
    AsyncTurnErrorEvent,
    AsyncTurnEvent,
    AsyncTurnFullResponseEvent,
    AsyncTurnMessageInsertedEvent,
    AsyncTurnRequestConfirmationEvent,
    AsyncTurnResponseChunkEvent,
    AsyncTurnResponseEndEvent,
    AsyncTurnResponseStartEvent,
    AsyncTurnToolCallEvent,
    AsyncTurnToolReturnEvent,
)
from bond.behaviours.async_turn_event_handler import AsyncTurnEventHandler
from bond.conversation.types import (
    AssistantMessageChunk,
    TextChunk,
    ThinkChunk,
    UserConversationMessage,
)

from . import logger


def _split_content(
    chunks: list[AssistantMessageChunk] | None,
) -> tuple[str | None, str | None]:
    """Split a chunk list into (text, thoughts)."""
    text_parts: list[str] = []
    think_parts: list[str] = []
    for chunk in chunks or []:
        if isinstance(chunk, TextChunk):
            text_parts.append(chunk.text)
        elif isinstance(chunk, ThinkChunk):
            think_parts.append(
                "".join(c.text for c in chunk.thinking if isinstance(c, TextChunk))
            )
    text = "".join(text_parts) or None
    think = "".join(think_parts) or None
    return text, think


class StdAsyncEventHandler(AsyncTurnEventHandler):
    """Prints async turn events to stdout, mirroring the old StdEventHandler."""

    def __init__(
        self,
        event_queue: asyncio.Queue[AsyncTurnEvent],
        show_thoughts: bool,
        show_tool_output: bool,
        is_interactive: bool = True,
        echo_user_message: bool = True,
    ):
        self._event_queue = event_queue
        self._show_thoughts = show_thoughts
        self._show_tool_output = show_tool_output
        self._is_interactive = is_interactive
        self._echo_user_message = echo_user_message
        self._has_open_thought_block = False
        self._task: asyncio.Task | None = None

    def is_running(self) -> bool:
        return self._task is not None

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        if self._task is not None:
            raise RuntimeError("Already running")
        if loop is None:
            loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())

    async def stop(self):
        if self._task is None:
            raise RuntimeError("Not running")
        task = self._task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def drain(self):
        """Process all events still sitting in the queue."""
        while not self._event_queue.empty():
            event = self._event_queue.get_nowait()
            logger.debug(f"Handling Event: {type(event)}")
            await event.dispatch(self)

    async def _run(self):
        try:
            while True:
                try:
                    event = await self._event_queue.get()
                    logger.debug(f"Handling Event: {type(event)}")
                    await event.dispatch(self)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        f"Event Handler caught Exception while processing {type(event)}"
                    )
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def handle_error_event(self, event: AsyncTurnErrorEvent):
        print(f"Error: {event.reason}", file=sys.stderr, flush=True)

    async def handle_full_response_event(self, event: AsyncTurnFullResponseEvent):
        message = event.message
        author = getattr(message, "name", "assistant")
        print(f"\n{author}:")
        inner = getattr(message, "message", None)
        content = getattr(inner, "content", None) if inner is not None else None
        text, think = _split_content(content)
        if think is not None and self._show_thoughts:
            print(f"[THINK]\n{think}\n[/THINK]")
        if text is not None:
            print(f"{text}\n")

    async def handle_message_inserted_event(self, event: AsyncTurnMessageInsertedEvent):
        message = event.message
        if self._echo_user_message and isinstance(message, UserConversationMessage):
            text, _ = _split_content(message.message.content)
            if text is not None:
                print(f"\n{message.name}:\n{text}\n")

    async def handle_request_confirmation_event(
        self, event: AsyncTurnRequestConfirmationEvent
    ):
        result = False
        if self._is_interactive:
            print(event.request)
            try:
                while True:
                    answer = await asyncio.to_thread(input, "[yes|no] > ")
                    if answer in ("yes", "y"):
                        result = True
                        break
                    if answer in ("no", "n"):
                        result = False
                        break
                    print("Invalid input.")
            except Exception as e:
                logger.error(e)
        event.result.set_result(result)

    async def handle_response_chunk_event(self, event: AsyncTurnResponseChunkEvent):
        if (
            len(event.chunk.choices) == 0
            or event.chunk.choices[0].delta.content is None
        ):
            return
        text, think = _split_content(event.chunk.choices[0].delta.content)
        if think is not None and self._show_thoughts:
            if not self._has_open_thought_block:
                print("[THINK]")
                self._has_open_thought_block = True
            print(think, end="", flush=True)
        if text is not None:
            if self._has_open_thought_block:
                print("\n[/THINK]")
                self._has_open_thought_block = False
            print(text, end="", flush=True)

    async def handle_response_end_event(self, event: AsyncTurnResponseEndEvent):
        if self._has_open_thought_block:
            print("\n[/THINK]")
            self._has_open_thought_block = False
        print("\n")

    async def handle_response_start_event(self, event: AsyncTurnResponseStartEvent):
        print(f"\n{event.author}:")
        self._has_open_thought_block = False

    async def handle_tool_call_event(self, event: AsyncTurnToolCallEvent):
        print(f"[Calling {event.tool_call.function.name}]")

    async def handle_tool_return_event(self, event: AsyncTurnToolReturnEvent):
        if self._show_tool_output:
            text, _ = _split_content(event.result.message.content)
            print(text if text is not None else event.result.message.content)
