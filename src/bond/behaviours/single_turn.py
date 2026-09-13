import logging

from returns.result import Failure, Result, Success

from bond.behaviours.auto_summarize import AutoSummarize
from bond.behaviours.behaviour_event import (
    AppendMessageChunkEvent,
    CallToolEvent,
    FullResponseEvent,
    ResponseEndEvent,
    ResponseStartEvent,
    ToolReturnEvent,
)
from bond.behaviours.behaviour_signal import InterruptSignal
from bond.behaviours.types import IBehaviourEventHandler, IBehaviourSignalReceiver
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (
    FunctionCall,
)
from bond.providers.provider import (
    ConversationPromptingStrategy,
)
from bond.runtime import BondRuntime
from bond.tools.shell_tools import allow_shell_commands
from bond.tools.tool import ToolCallContext
from bond.tools.toolbox import Toolbox

logger = logging.getLogger(__name__)


def _do_tool_call(
    toolbox: Toolbox, function_call: FunctionCall, context: ToolCallContext
) -> str:
    result = toolbox.call_tool(function_call.name, function_call.arguments, context)
    logger.info(f"Tool call returned object of type {type(result)}\n{result}")
    if isinstance(result, Success):
        return result.unwrap()
    else:
        return f"Error during tool execution: {result.failure()}"


class SingleTurn:
    def __init__(
        self,
        conversation_prompt: ConversationPromptingStrategy,
        auto_summarize: AutoSummarize | None,
        author_name: str,
        event_handler: IBehaviourEventHandler,
        signal_receiver: IBehaviourSignalReceiver,
        tool_call_context: ToolCallContext,
        toolbox: Toolbox,
        stream: bool = False,
        allow_shell_executions: bool = False,
        runtime: BondRuntime | None = None,
    ):
        self._conversation_prompt = conversation_prompt
        self._auto_summarize = auto_summarize
        self._author_name = author_name
        self._event_handler = event_handler
        self._signal_receiver = signal_receiver
        self._tool_call_context = tool_call_context
        self._toolbox = toolbox
        self._stream = stream
        self._allow_shell_executions = allow_shell_executions
        self._runtime = runtime or BondRuntime.get_instance()

        self._tool_descriptions = self._toolbox.get_tool_descriptions()

    def run(self, conversation: Conversation) -> Result[None, str]:
        stream_callback = (
            (lambda chunk: self._event_handler(AppendMessageChunkEvent(chunk=chunk)))
            if self._stream
            else None
        )
        while True:
            signal = self._signal_receiver.peek()
            if signal is not None and isinstance(signal, InterruptSignal):
                self._signal_receiver.get()
                return Success(None)

            if self._stream:
                self._event_handler(
                    ResponseStartEvent(author=self._author_name, role="assistant")
                )
            response = self._conversation_prompt(conversation, stream_callback)
            if isinstance(response, Failure):
                return response
            response = response.unwrap()
            self._event_handler(
                ResponseEndEvent(usage=response.usage)
                if self._stream
                else FullResponseEvent(
                    author=self._author_name, role="assistant", response=response
                )
            )

            if self._auto_summarize is not None:
                result = self._auto_summarize.run(conversation)
                if isinstance(result, Failure):
                    logger.warning(
                        f"Could not create summarization: {result.failure()}"
                    )

            message = response.choices[0].message

            # Return when no tools are called
            if message.tool_calls is None:
                return Success(None)

            # Handle Tool calls
            for tool_call in message.tool_calls:
                self._event_handler(CallToolEvent(call=tool_call))
                if self._allow_shell_executions:
                    with allow_shell_commands():
                        result = _do_tool_call(
                            self._toolbox, tool_call.function, self._tool_call_context
                        )
                else:
                    result = _do_tool_call(
                        self._toolbox, tool_call.function, self._tool_call_context
                    )

                self._event_handler(ToolReturnEvent(result=result))
                conversation.add_message(
                    ConversationMessage.create_tool_response_message(result, tool_call)
                )
