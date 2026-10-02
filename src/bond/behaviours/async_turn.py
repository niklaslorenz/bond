import asyncio
import logging

from returns.result import Failure, Result, Success

from bond.behaviours.async_turn_event import *
from bond.behaviours.auto_summarize import AutoSummarization
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (
    FunctionCall,
    TextChunk,
    ToolCall,
)
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse
from bond.persona import Persona
from bond.runtime import BondRuntime
from bond.tools.shell_tools import allow_shell_commands
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox

logger = logging.getLogger(__name__)


class AsyncAgentTurn:
    def __init__(
        self,
        persona: Persona,
        tool_call_context: ToolCallContext,
        event_queue: asyncio.Queue[AsyncTurnEvent],
        runtime: BondRuntime | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self._persona = persona
        self._tool_call_context = tool_call_context
        self._event_queue = event_queue
        self._loop = loop or asyncio.get_event_loop()
        self._runtime = runtime or BondRuntime.get_instance()
        self._generation = persona.generation
        self._auto_summarize = (
            AutoSummarization(persona.summarization)
            if persona.summarization is not None
            else None
        )
        self._tts = persona.tts

        self._stream = self._runtime.behaviour_flags.stream
        self._allow_shell_executions = (
            self._runtime.behaviour_flags.allow_shell_executions
        )

        self._running = False
        self._ask_for_stop: bool = False

    def stop(self):
        self._ask_for_stop = True

    async def run(self, conversation: Conversation) -> Result[None, str]:
        if self._running:
            raise RuntimeError("Already running")
        self._running = True
        self._ask_for_stop = False
        try:
            while not self._ask_for_stop:
                logger.debug("Agent Turn Loop Start")
                response_result = await self._prompt_response(conversation)
                logger.debug("Response complete")
                if isinstance(response_result, Failure):
                    return response_result
                response, _ = response_result.unwrap()
                await self._summarize(conversation)

                # Return when no tools are called
                if response.choices[0].message.tool_calls is None:
                    logger.debug("No tool calls. Finishing Turn")
                    return Success(None)

                await self._handle_tool_calls(
                    response.choices[0].message.tool_calls, conversation
                )
        except asyncio.CancelledError:
            logger.info("Agent turn interrupted")
            return Failure("Agent turn cancelled")
        except BaseException as e:
            await self._event_queue.put(AsyncTurnErrorEvent(f"({type(e)}): {e}"))
            logger.error(f"Error during agent turn ({type(e)}): {e}")
            return Failure(f"Error during agent turn ({type(e)}): {e}")
        finally:
            self._running = False
        return Failure("Agent turn stopped")

    async def _prompt_response(
        self, conversation: Conversation
    ) -> Result[tuple[CompletionResponse, ConversationMessage], str]:
        if self._stream:
            await self._event_queue.put(
                AsyncTurnResponseStartEvent(author=self._persona.name, role="assistant")
            )

        def insert_chunk(chunk: CompletionChunk):
            asyncio.run_coroutine_threadsafe(
                self._event_queue.put(AsyncTurnResponseChunkEvent(chunk=chunk)),
                self._loop,
            )

        response = await self._loop.run_in_executor(
            None,
            self._generation,
            conversation,
            insert_chunk if self._stream else None,
        )
        if isinstance(response, Failure):
            await self._event_queue.put(AsyncTurnErrorEvent(response.failure()))
        else:
            raw_response, message = response.unwrap()
            conversation.add_message(message)
            conversation.current_usage = raw_response.usage.total_tokens
            await self._event_queue.put(
                AsyncTurnResponseEndEvent(raw_response.usage)
                if self._stream
                else AsyncTurnFullResponseEvent(message=message, response=raw_response)
            )
            if self._tts is not None:
                text = "".join(
                    chunk.text
                    for chunk in message.message.content or []
                    if isinstance(chunk, TextChunk)
                ).strip()
                if text:
                    audio = self._tts(text)
                    if isinstance(audio, Success):
                        self._loop.run_in_executor(None, audio.unwrap().play)
                    else:
                        logger.error(audio.failure())
        return response

    async def _summarize(self, conversation: Conversation):
        if self._auto_summarize is not None:
            await self._event_queue.put(AsyncTurnAutoSummaryEvent(False))
            result = await self._loop.run_in_executor(
                None, self._auto_summarize.run, conversation
            )
            if isinstance(result, Failure):
                logger.warning(f"Could not create summarization: {result.failure()}")
            await self._event_queue.put(AsyncTurnAutoSummaryEvent(True))

    async def _handle_tool_calls(
        self,
        tool_calls: list[ToolCall],
        conversation: Conversation,
    ):
        for tool_call in tool_calls:
            await self._event_queue.put(AsyncTurnToolCallEvent(tool_call))
            if self._allow_shell_executions:
                with allow_shell_commands():
                    result = await self._loop.run_in_executor(
                        None,
                        _do_tool_call,
                        self._persona.toolbox,
                        tool_call.function,
                        self._tool_call_context,
                    )
            else:
                result = await self._loop.run_in_executor(
                    None,
                    _do_tool_call,
                    self._persona.toolbox,
                    tool_call.function,
                    self._tool_call_context,
                )

            message = ConversationMessage.create_tool_response_message(
                (
                    result.unwrap()
                    if isinstance(result, Success)
                    else f"Failure: {result.failure()}"
                ),
                tool_call,
            )
            conversation.add_message(message)
            await self._event_queue.put(AsyncTurnToolReturnEvent(result=message))


def _do_tool_call(
    toolbox: Toolbox, function_call: FunctionCall, context: ToolCallContext
) -> Result[str, str]:
    result = toolbox.call_tool(function_call.name, function_call.arguments, context)

    if isinstance(result, Failure):
        logger.info(f"Tool call failed: {result.failure()}")
    return result
