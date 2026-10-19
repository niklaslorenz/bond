import asyncio
import logging

from returns.result import Failure, Result, Success

from bond.behaviours.async_turn_event import *
from bond.behaviours.types import TurnStatus
from bond.capabilities.generation import GenerationTriggers
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    TextChunk,
    Turn,
)
from bond.endpoints.chat_completions import CompletionChunk
from bond.observable import Observable
from bond.persona import Persona
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext

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
        self._lock = asyncio.Lock()
        self._persona = persona
        self._tool_call_context = tool_call_context
        self._event_queue = event_queue
        self._loop = loop or asyncio.get_event_loop()
        self._runtime = runtime or BondRuntime.get_instance()
        self._generation = persona.generation
        self._tts = persona.tts

        self._stream = self._runtime.behaviour_flags.stream
        self._allow_shell_executions = (
            self._runtime.behaviour_flags.allow_shell_executions
        )
        self._turn_status: Observable[TurnStatus] = Observable("Stopped")

    @property
    def is_running(self) -> bool:
        return self._lock.locked()

    @property
    def turn_status(self) -> Observable[TurnStatus]:
        return self._turn_status

    async def run(
        self, conversation: Conversation, triggers: GenerationTriggers
    ) -> Result[Turn, str]:
        if self.is_running:
            raise RuntimeError("Already running")
        async with self._lock:
            try:
                logger.debug("Starting agent turn")
                self._turn_status.value = "Receiving"
                response_result = await self._prompt_response(conversation, triggers)
                if isinstance(response_result, Failure):
                    return response_result
                response = response_result.unwrap()
                await self._play_tts(response)
                turn = Turn(
                    tool_messages=triggers.tool_messages,
                    user_message=triggers.user_message,
                    assistant_response=response,
                )
                conversation.add_turn(turn)
                self._turn_status.value = "Summarizing"
                condensed_thoughts = await self._condense_thoughts(conversation)
                response.condensed_thoughts = condensed_thoughts
                await self.summarize(conversation, False)
                logger.debug("Finished Agent Turn")
                return Success(turn)
            except asyncio.CancelledError:
                logger.info("Agent turn interrupted")
                return Failure("Agent turn cancelled")
            except BaseException as e:
                await self._event_queue.put(AsyncTurnErrorEvent(f"({type(e)}): {e}"))
                logger.error(f"Error during agent turn ({type(e)}): {e}")
                return Failure(f"Error during agent turn ({type(e)}): {e}")
            finally:
                self._turn_status.value = "Stopped"

    async def _play_tts(self, response: AssistantConversationMessage):
        if self._tts is not None:
            text = "".join(
                chunk.text
                for chunk in response.message.content or []
                if isinstance(chunk, TextChunk)
            ).strip()
            if text:
                audio = self._tts(text)
                if isinstance(audio, Success):
                    self._loop.run_in_executor(None, audio.unwrap().play)
                else:
                    logger.error(audio.failure())

    async def _condense_thoughts(self, conversation: Conversation) -> str | None:
        summarization = self._persona.summarization
        if summarization is None:
            return None
        result = summarization.condense_thoughts(conversation)
        if result is None:
            return None
        if isinstance(result, Failure):
            logger.error(f"Could not condense thoughts: {result.failure()}")
            return None
        return result.unwrap()

    async def _prompt_response(
        self, conversation: Conversation, triggers: GenerationTriggers
    ) -> Result[AssistantConversationMessage, str]:
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
            self._generation.generate,
            conversation,
            triggers,
            insert_chunk if self._stream else None,
        )
        if isinstance(response, Failure):
            await self._event_queue.put(AsyncTurnErrorEvent(response.failure()))
        else:
            message = response.unwrap()
            await self._event_queue.put(
                AsyncTurnResponseEndEvent(message.usage)
                if self._stream
                else AsyncTurnFullResponseEvent(message=message)
            )
        return response

    async def summarize(
        self, conversation: Conversation, force: bool
    ) -> Result[int, str] | None:
        summarize = self._persona.summarization
        if summarize is None:
            return
        result = await self._loop.run_in_executor(
            None, summarize.summarize_episode, conversation, force
        )
        if result is not None and isinstance(result, Failure):
            logger.warning(f"Could not create summarization: {result.failure()}")
        return result
