import asyncio
from typing import Callable

from returns.result import Result

from bond.behaviours import auto_summarize
from bond.behaviours.async_turn import AsyncAgentTurn, AsyncTurnEvent
from bond.behaviours.auto_summarize import AutoSummarize
from bond.behaviours.behaviour_event import (
    ChangePersonaEvent,
    CommandResponseEvent,
    ErrorEvent,
    NotifyEvent,
    RestoreConversationEvent,
    StopEvent,
    WaitingForInputEvent,
)
from bond.behaviours.behaviour_signal import CommandSignal, PromptSignal, StopSignal
from bond.behaviours.single_turn import SingleTurn
from bond.behaviours.types import IBehaviourEventHandler, IBehaviourSignalReceiver
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import UserMessage
from bond.persona import Persona
from bond.providers.provider import ConversationSummarizationStrategy
from bond.runtime import BondRuntime
from bond.tools.tool import ToolCallContext

from . import logger


class AsyncAgentLoop:

    def __init__(
        self,
        runtime: BondRuntime,
        conversation: Conversation,
        tool_call_context: ToolCallContext,
        event_queue: asyncio.Queue[AsyncTurnEvent],
        default_persona_id: str,
        stream: bool = False,
        allow_shell_executions: bool = False,
        user_name: str | None = None,
        save_after_turn: bool = False,
    ):
        self._runtime = runtime
        self._conversation = conversation
        self._tool_call_context = tool_call_context
        self._event_queue = event_queue
        self._default_persona_id = default_persona_id
        self._stream = stream
        self._allow_shell_executions = allow_shell_executions
        self._user_name = user_name
        self._save_after_turn = save_after_turn

        self._running = False
        self._current_turn: asyncio.Task[Result[None, str]] | None = None
        self._agent_turn: AsyncAgentTurn = self._build_turn()

    def _build_turn(self) -> AsyncAgentTurn:
        if self._running:
            raise RuntimeError("Cant build turn while running")
        persona_id = self._conversation.current_persona or self._default_persona_id
        persona = self._runtime.get_persona(persona_id)
        provider = self._runtime.get_provider(persona.provider)
        toolbox = self._runtime.build_toolbox(persona.toolbox)
        prompting = provider.conversation_prompting(persona, toolbox)
        assert prompting
        if persona.summarization:
            summarizing = provider.conversation_summarization(persona)
            assert summarizing
            auto_summarize = (
                AutoSummarize(
                    persona.summarization.auto_summarize,
                    summarizing,
                    persona.summarization.keep,
                )
                if persona.summarization.auto_summarize is not None
                else None
            )
        else:
            summarizing = None
            auto_summarize = None

        self._tool_call_context.persona = persona_id

        return AsyncAgentTurn(
            prompting,
            auto_summarize,
            persona.name,
            self._tool_call_context,
            toolbox,
            self._event_queue,
            self._stream,
            self._allow_shell_executions,
            self._runtime,
        )

    def set_persona(self, persona_id: str):
        if self._running:
            raise RuntimeError("Cant change persona while running")
        self._conversation.current_persona = persona_id
        self._agent_turn = self._build_turn()

    def set_conversation(self, conversation: Conversation):
        if self._running:
            raise RuntimeError("Cant change conversation while running")
        self._conversation = conversation
        self._agent_turn = self._build_turn()
        pass

    def new_conversation(self, persona_id: str | None = None):
        if self._running:
            raise RuntimeError("Cant change conversation while running")
        self.set_conversation(
            Conversation(
                current_persona=persona_id or self._conversation.current_persona
            )
        )

    def cancel(self):
        if self._running:
            assert self._current_turn
            self._current_turn.cancel()

    async def prompt(self, message: UserMessage) -> Result[None, str]:
        if self._running:
            raise RuntimeError("Already running")
        loop = asyncio.get_event_loop()
        self._conversation.add_message(
            ConversationMessage(message=message, author=self._user_name)
        )
        try:
            self._running = True
            turn_task = loop.create_task(self._agent_turn.run(self._conversation))
            self._current_turn = turn_task
            return await turn_task
        finally:
            self._current_turn = None
            self._running = False
