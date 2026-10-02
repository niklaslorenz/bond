import asyncio
import logging

from returns.result import Failure, Result

from bond.behaviours.async_turn import AsyncAgentTurn, AsyncTurnEvent
from bond.behaviours.async_turn_event import (
    AsyncTurnErrorEvent,
    AsyncTurnMessageInsertedEvent,
)
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import UserMessage
from bond.persona import Persona
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


class AsyncAgentLoop:

    def __init__(
        self,
        runtime: BondRuntime,
        conversation: Conversation,
        tool_call_context: ToolCallContext,
        event_queue: asyncio.Queue[AsyncTurnEvent],
        event_loop: asyncio.AbstractEventLoop,
        default_persona_id: str,
        user_name: str | None = None,
        save_after_turn: bool = False,
    ):
        self._runtime = runtime
        self._conversation = conversation
        self._tool_call_context = tool_call_context
        self._event_queue = event_queue
        self._event_loop = event_loop
        self._default_persona_id = default_persona_id
        self._user_name = user_name
        self._save_after_turn = save_after_turn

        self._stream = runtime.behaviour_flags.stream
        self._allow_shell_executions = runtime.behaviour_flags.allow_shell_executions

        self._lock = asyncio.Lock()
        self._current_task: asyncio.Task | None = None
        self._agent_turn, self._persona = self._build_turn()

    @property
    def lock(self):
        return self._lock

    @property
    def conversation(self):
        return self._conversation

    @property
    def persona(self):
        return self._persona

    async def wait_for(self):
        if not self._lock.locked():
            return
        assert self._current_turn is not None
        await self._current_turn

    async def set_persona(self, persona_id: str):
        async with self._lock:
            self._conversation.current_persona = persona_id
            self._agent_turn, self._persona = self._build_turn()

    async def set_conversation(self, conversation: Conversation):
        async with self._lock:
            self._conversation = conversation
            self._agent_turn, self._persona = self._build_turn()

    async def new_conversation(self, persona_id: str | None = None):
        await self.set_conversation(
            Conversation(
                current_persona=persona_id or self._conversation.current_persona
            )
        )

    async def cancel(self):
        if self.lock.locked():
            assert self._current_turn
            self._current_turn.cancel()
            self._current_turn = None

    async def prompt(self, message: UserMessage) -> Result[None, str]:
        logger.debug("Triggered AsyncLoop.prompt")
        async with self._lock:
            logger.debug("Acquired lock")
            try:
                conv_msg = ConversationMessage(message=message, author=self._user_name)
                self._conversation.add_message(conv_msg)
                await self._event_queue.put(AsyncTurnMessageInsertedEvent(conv_msg))
                task = asyncio.create_task(self._agent_turn.run(self._conversation))
                self._current_turn = task
                logger.debug("Waiting for prompt completion")
                result = await task
                logger.debug("prompt completed")
                self._current_turn = None
                return result
            finally:
                self._current_turn = None

    async def summarize(self) -> Result[str, str]:
        if self._persona.summarization:
            async with self._lock:
                try:
                    task = asyncio.get_event_loop().run_in_executor(
                        None, self._persona.summarization, self.conversation
                    )
                    self._current_turn = task
                    result = await task
                    self._current_turn = None
                    return result
                finally:
                    self._current_turn = None
        else:
            return Failure("Summarization is not enabled")

    def _build_turn(self) -> tuple[AsyncAgentTurn, Persona]:
        persona_id = self._conversation.current_persona or self._default_persona_id
        persona_config = self._runtime.get_persona(persona_id)
        if isinstance(persona_config, Failure):
            self._event_queue.put_nowait(AsyncTurnErrorEvent(persona_config.failure()))
            return self._agent_turn, self._persona
        persona_config = persona_config.unwrap()
        persona = persona_config.instantiate()

        # TODO: this is just a dirty hack, there has to be a better solution
        self._tool_call_context.persona = persona_id
        self._tool_call_context.conversation = self.conversation

        return (
            AsyncAgentTurn(
                persona,
                self._tool_call_context,
                self._event_queue,
                self._runtime,
                self._event_loop,
            ),
            persona,
        )
