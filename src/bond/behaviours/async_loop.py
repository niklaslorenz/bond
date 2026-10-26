import asyncio
import logging
from contextlib import asynccontextmanager

from returns.result import Failure, Result, Success

from bond.behaviours.async_turn import AsyncAgentTurn, AsyncTurnEvent
from bond.behaviours.async_turn_event import (
    AsyncTurnErrorEvent,
    AsyncTurnMessageInsertedEvent,
    AsyncTurnToolCallEvent,
    AsyncTurnToolReturnEvent,
)
from bond.behaviours.types import (
    AsyncLoopSignalBuffer,
    LoopStatus,
    PauseRequest,
    StopSignal,
    TurnStatus,
)
from bond.capabilities.generation import GenerationTriggers
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    FunctionCall,
    TextChunk,
    ToolCall,
    ToolConversationMessage,
    ToolMessage,
    UserConversationMessage,
)
from bond.observable import Observable
from bond.persona import Persona
from bond.runtime import BondRuntime
from bond.tools.shell_tools import allow_shell_commands
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox

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
        *,
        stream: bool,
        allow_shell_executions: bool,
        save_after_turn: bool,
        stop_on_failure: bool,
    ):
        self._runtime = runtime
        self._conversation = conversation
        self._tool_call_context = tool_call_context
        self._event_queue = event_queue
        self._event_loop = event_loop
        self._default_persona_id = default_persona_id
        self._save_after_turn = save_after_turn
        self._stop_on_failure = stop_on_failure

        self._signal_buffer = AsyncLoopSignalBuffer()
        self._task: asyncio.Task | None = None
        self._stopped_event = asyncio.Event()
        self._pause_owner: asyncio.Task | None = None
        self._pause_lock = asyncio.Lock()
        self._pause_depth = 0
        self._loop_status: Observable[LoopStatus] = Observable("Stopped")

        self._stream = stream
        self._allow_shell_executions = allow_shell_executions

        self._agent_turn, self._persona = self._build_turn()

    @property
    def is_running(self) -> bool:
        return self._task is not None

    @property
    def conversation(self) -> Conversation:
        return self._conversation

    @property
    def persona(self) -> Persona:
        return self._persona

    async def set_persona(self, persona_id: str):
        async with self.pause():
            self._conversation.persona = persona_id
            self._agent_turn, self._persona = self._build_turn()
            self._signal_buffer._clear()

    async def set_conversation(self, conversation: Conversation):
        async with self.pause():
            self._conversation = conversation
            self._agent_turn, self._persona = self._build_turn()
            self._signal_buffer._clear()

    @property
    def is_idle(self):
        return self._signal_buffer.has_waiter()

    @property
    def loop_status(self):
        return self._loop_status

    def prompt(self, message: UserConversationMessage) -> Result[None, str]:
        return self._signal_buffer.signal_user_input(message)

    async def stop(self, immediate: bool = False):
        if not self.is_running:
            return
        self._signal_buffer.signal_stop(immediate)
        await self._stopped_event.wait()
        assert not self.is_running

    async def cancel(self):
        if self.is_running:
            assert self._task is not None
            task = self._task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def start(self):
        if self._task is not None:
            raise RuntimeError("Already running")
        async with self._pause_lock:
            self._signal_buffer = AsyncLoopSignalBuffer()
            self._stopped_event.clear()
            self._pause_owner = None
            self._pause_depth = 0
            self._task = self._event_loop.create_task(self._run())

    @asynccontextmanager
    async def pause(self):
        task = asyncio.current_task()

        if self._pause_owner is task:
            self._pause_depth += 1
            try:
                yield
            finally:
                self._pause_depth -= 1
            return

        async with self._pause_lock:
            self._pause_owner = task
            self._pause_depth = 1

            request = PauseRequest()
            try:
                if self.is_running:
                    self._signal_buffer.request_pause(request)
                    await request.wait_until_paused()
                    logger.debug("Paused Agent Loop")
                yield
            finally:
                request.resume()
                self._pause_owner = None
                self._pause_depth = 0

    def interrupt(self):
        if not self.is_running:
            raise RuntimeError("Not running")
        self._signal_buffer.interrupt()

    async def _run(self):
        try:
            while True:
                self._loop_status.value = "Idle"
                signal = await self._signal_buffer.pull()
                if isinstance(signal, StopSignal):
                    break
                if isinstance(signal, PauseRequest):
                    self._is_paused = True
                    try:
                        signal.paused()
                        self._loop_status.value = "Paused"
                        await signal.wait_until_resume()
                    finally:
                        self._is_paused = False
                    continue
                if not isinstance(signal, GenerationTriggers):
                    raise RuntimeError(f"Invalid signal type: {type(signal)}")

                self._loop_status.value = "Waiting"
                if signal.user_message is not None:
                    await self._event_queue.put(
                        AsyncTurnMessageInsertedEvent(message=signal.user_message)
                    )

                turn = await self._agent_turn.run(self.conversation, signal)
                if isinstance(turn, Failure):
                    logger.error(f"Error during agent turn: {turn.failure()}")
                    await self._event_queue.put(
                        AsyncTurnErrorEvent(
                            "The agent loop has crashed. Please view the logs to see the reason."
                        )
                    )
                    if self._stop_on_failure:
                        break
                    else:
                        continue
                turn = turn.unwrap()
                tool_calls = turn.assistant_response.message.tool_calls
                self._loop_status.value = "Tool Call"
                if tool_calls is not None:
                    tool_messages, _ = await self._handle_tool_calls(tool_calls)
                    self._signal_buffer.signal_tool_outputs(tool_messages)
        finally:
            self._loop_status.value = "Stopped"
            self._task = None
            self._stopped_event.set()
            self._signal_buffer.release()

    async def summarize(self) -> Result[int, str] | None:
        async with self.pause():
            return await self._agent_turn.summarize(self.conversation, True)

    def _on_turn_status_update(self, status: TurnStatus):
        if status == "Stopped":
            self._loop_status.value = "Waiting"
        else:
            self._loop_status.value = status
        pass

    def _build_turn(self) -> tuple[AsyncAgentTurn, Persona]:
        if self.is_running and not self._is_paused:
            raise RuntimeError("Cannot rebuild turn while busy")
        persona_id = self._conversation.persona or self._default_persona_id
        persona_config = self._runtime.get_persona(persona_id)
        if isinstance(persona_config, Failure):
            self._event_queue.put_nowait(AsyncTurnErrorEvent(persona_config.failure()))
            raise RuntimeError(f"Invalid persona config: {persona_config.failure()}")
        persona_config = persona_config.unwrap()
        persona = persona_config.instantiate()

        # TODO: this is just a dirty hack, there has to be a better solution
        self._tool_call_context.persona = persona
        self._tool_call_context.conversation = self.conversation

        if hasattr(self, "_agent_turn"):
            getattr(self, "_agent_turn").turn_status.unsubscribe(
                self._on_turn_status_update
            )

        if hasattr(self, "_persona"):
            getattr(self, "_persona").release()

        turn = AsyncAgentTurn(
            persona,
            self._tool_call_context,
            self._event_queue,
            self._stream,
            self._allow_shell_executions,
            self._runtime,
            self._event_loop,
        )
        turn.turn_status.subscribe(self._on_turn_status_update)
        if self.conversation.persona is None:
            self.conversation.persona = persona_id
        return (turn, persona)

    async def _handle_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> tuple[list[ToolConversationMessage], list[str]]:
        results = []
        messages = []
        for tool_call in tool_calls:
            await self._event_queue.put(AsyncTurnToolCallEvent(tool_call))
            if self._allow_shell_executions:
                with allow_shell_commands():
                    result = await self._event_loop.run_in_executor(
                        None,
                        _do_tool_call,
                        self._persona.toolbox,
                        tool_call.function,
                        self._tool_call_context,
                    )
            else:
                result = await self._event_loop.run_in_executor(
                    None,
                    _do_tool_call,
                    self._persona.toolbox,
                    tool_call.function,
                    self._tool_call_context,
                )

            res = (
                result.unwrap()
                if isinstance(result, Success)
                else f"Failure: {result.failure()}"
            )
            results.append(res)
            message = _build_tool_message(tool_call, res)
            messages.append(message)
            await self._event_queue.put(AsyncTurnToolReturnEvent(result=message))
        return messages, results


def _do_tool_call(
    toolbox: Toolbox, function_call: FunctionCall, context: ToolCallContext
) -> Result[str, str]:
    result = toolbox.call_tool(function_call.name, function_call.arguments, context)

    if isinstance(result, Failure):
        logger.info(f"Tool call failed: {result.failure()}")
    return result


def _build_tool_message(
    tool_call: ToolCall, tool_return: str
) -> ToolConversationMessage:
    return ToolConversationMessage(
        message=ToolMessage(
            tool_call_id=tool_call.id,
            name=tool_call.function.name,
            content=[TextChunk(text=tool_return)],
        )
    )
