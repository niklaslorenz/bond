import asyncio
import logging
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from bond.behaviours.auto_summarize import AutoSummarize
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (
    FunctionCall,
    ToolCall,
    UsageInfo,
)
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse
from bond.providers.provider import (
    ConversationPromptingStrategy,
)
from bond.runtime import BondRuntime
from bond.tools.shell_tools import allow_shell_commands
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox

logger = logging.getLogger(__name__)


@dataclass
class AsyncTurnResponseChunkEvent:
    chunk: CompletionChunk


@dataclass
class AsyncTurnResponseStartEvent:
    author: str
    role: str


@dataclass
class AsyncTurnErrorEvent:
    reason: str


@dataclass
class AsyncTurnResponseEndEvent:
    usage: UsageInfo


@dataclass
class AsyncTurnFullResponseEvent:
    author: str
    role: str
    response: CompletionResponse


@dataclass
class AsyncTurnToolCallEvent:
    tool_call: ToolCall


@dataclass
class AsyncTurnToolReturnEvent:
    result: Result[str, str]


@dataclass
class AsyncTurnAutoSummaryEvent:
    finished: bool


AsyncTurnEvent = (
    AsyncTurnResponseChunkEvent
    | AsyncTurnResponseStartEvent
    | AsyncTurnErrorEvent
    | AsyncTurnResponseEndEvent
    | AsyncTurnFullResponseEvent
    | AsyncTurnToolCallEvent
    | AsyncTurnToolReturnEvent
    | AsyncTurnAutoSummaryEvent
)


class AsyncAgentTurn:
    def __init__(
        self,
        conversation_prompt: ConversationPromptingStrategy,
        auto_summarize: AutoSummarize | None,
        author_name: str,
        tool_call_context: ToolCallContext,
        toolbox: Toolbox,
        event_queue: asyncio.Queue[AsyncTurnEvent],
        stream: bool = False,
        allow_shell_executions: bool = False,
        runtime: BondRuntime | None = None,
    ):
        self._conversation_prompt = conversation_prompt
        self._auto_summarize = auto_summarize
        self._author_name = author_name
        self._tool_call_context = tool_call_context
        self._toolbox = toolbox
        self._event_queue = event_queue
        self._stream = stream
        self._allow_shell_executions = allow_shell_executions
        self._runtime = runtime or BondRuntime.get_instance()

        self._tool_descriptions = self._toolbox.tool_descriptions
        self._running = False
        self._ask_for_stop: bool = False

    def stop(self):
        self._ask_for_stop = True

    async def run(self, conversation: Conversation) -> Result[None, str]:
        if self._running:
            raise RuntimeError("Already running")
        self._running = True
        self._ask_for_stop = False
        loop = asyncio.get_event_loop()
        try:
            while not self._ask_for_stop:
                response = await self._prompt_response(loop, conversation)
                if isinstance(response, Failure):
                    return response
                response = response.unwrap()
                await self._summarize(loop, conversation)
                message = response.choices[0].message

                # Return when no tools are called
                if message.tool_calls is None:
                    return Success(None)

                await self._handle_tool_calls(message.tool_calls, loop, conversation)
        except asyncio.CancelledError:
            logger.info("Agent turn interrupted")
            return Failure("Agent turn cancelled")
        except BaseException as e:
            await self._event_queue.put(AsyncTurnErrorEvent(f"({type(e)}): {e}"))
            return Failure(f"Error during agent turn ({type(e)}): {e}")
        finally:
            self._running = False
        return Failure("Agent turn stopped")

    async def _prompt_response(
        self, loop: asyncio.AbstractEventLoop, conversation: Conversation
    ) -> Result[CompletionResponse, str]:
        if self._stream:
            await self._event_queue.put(
                AsyncTurnResponseStartEvent(author=self._author_name, role="assistant")
            )

        def insert_chunk(chunk: CompletionChunk):
            asyncio.run(self._event_queue.put(AsyncTurnResponseChunkEvent(chunk=chunk)))

        response = await loop.run_in_executor(
            None,
            self._conversation_prompt,
            conversation,
            insert_chunk if self._stream else None,
        )
        if isinstance(response, Failure):
            await self._event_queue.put(AsyncTurnErrorEvent(response.failure()))
        else:
            unwrapped = response.unwrap()
            await self._event_queue.put(
                AsyncTurnResponseEndEvent(unwrapped.usage)
                if self._stream
                else AsyncTurnFullResponseEvent(
                    author=self._author_name, role="assistant", response=unwrapped
                )
            )
        return response

    async def _summarize(
        self, loop: asyncio.AbstractEventLoop, conversation: Conversation
    ):
        if self._auto_summarize is not None:
            await self._event_queue.put(AsyncTurnAutoSummaryEvent(False))
            result = await loop.run_in_executor(
                None, self._auto_summarize.run, conversation
            )
            if isinstance(result, Failure):
                logger.warning(f"Could not create summarization: {result.failure()}")
            await self._event_queue.put(AsyncTurnAutoSummaryEvent(True))

    async def _handle_tool_calls(
        self,
        tool_calls: list[ToolCall],
        loop: asyncio.AbstractEventLoop,
        conversation: Conversation,
    ):
        for tool_call in tool_calls:
            await self._event_queue.put(AsyncTurnToolCallEvent(tool_call))
            if self._allow_shell_executions:
                with allow_shell_commands():
                    result = await loop.run_in_executor(
                        None,
                        _do_tool_call,
                        self._toolbox,
                        tool_call.function,
                        self._tool_call_context,
                    )
            else:
                result = await loop.run_in_executor(
                    None,
                    _do_tool_call,
                    self._toolbox,
                    tool_call.function,
                    self._tool_call_context,
                )

            await self._event_queue.put(AsyncTurnToolReturnEvent(result=result))
            conversation.add_message(
                ConversationMessage.create_tool_response_message(
                    (
                        result.unwrap()
                        if isinstance(result, Success)
                        else f"Failure: {result.failure()}"
                    ),
                    tool_call,
                )
            )


def _do_tool_call(
    toolbox: Toolbox, function_call: FunctionCall, context: ToolCallContext
) -> Result[str, str]:
    result = toolbox.call_tool(function_call.name, function_call.arguments, context)

    if isinstance(result, Failure):
        logger.info(f"Tool call failed: {result.failure()}")
    return result
