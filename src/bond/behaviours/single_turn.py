import logging

from returns.result import Success

from bond.behaviours.behaviour_event import (AppendMessageChunkEvent,
                                             BehaviourEventHandler,
                                             CallToolEvent, FullResponseEvent,
                                             ResponseEndEvent,
                                             ResponseStartEvent,
                                             ToolReturnEvent)
from bond.behaviours.behaviour_signal import (BehaviourSignalReceiver,
                                              InterruptSignal)
from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (AssistantMessage, FunctionCall,
                                     SystemMessage)
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.tools import tool
from bond.tools.shell import allow_shell_commands
from bond.tools.tool import Toolbox, ToolEnvironment

logger = logging.getLogger(__name__)


def _do_tool_call(toolbox: Toolbox, function_call: FunctionCall) -> str:
    result = toolbox.call_tool(function_call.name, function_call.arguments)
    logger.info(f"Tool call returned object of type {type(result)}\n{result}")
    if isinstance(result, Success):
        return result.unwrap()
    else:
        return f"Error during tool execution: {result.failure()}"


class SingleTurn:
    def __init__(
        self,
        endpoint: ChatCompletionsEndpoint,
        model: str,
        event_handler: BehaviourEventHandler,
        signal_receiver: BehaviourSignalReceiver,
        tool_environment: ToolEnvironment,
        system_message: str | None = None,
        toolbox: Toolbox | None = None,
        model_display_name: str | None = None,
        stream: bool = False,
        allow_shell_executions: bool = False,
        **additional_chat_completion_arguments,
    ):
        self.endpoint = endpoint
        self.model = model
        self.event_handler = event_handler
        self.signal_receiver = signal_receiver
        self.system_message = system_message
        self.toolbox = toolbox if toolbox is not None else Toolbox({})
        self.tool_descriptions = self.toolbox.get_tool_descriptions()
        self.tool_environment = tool_environment
        self.model_display_name = model_display_name
        self.stream = stream
        self.allow_shell_executions = allow_shell_executions
        self.additional_model_arguments = additional_chat_completion_arguments

        if stream and not self.endpoint.supports_streaming():
            raise RuntimeError(
                "The provider does not support streaming for chat completions"
            )

    def run(self, conversation: Conversation) -> Conversation:
        while True:
            signal = self.signal_receiver.peek()
            if signal is not None and isinstance(signal, InterruptSignal):
                self.signal_receiver.get()
                return conversation

            system_msg = (
                SystemMessage.create(self.system_message)
                if self.system_message is not None
                else None
            )
            if self.stream:
                self.event_handler(
                    ResponseStartEvent(
                        author=self.model_display_name or "Assistant", role="assistant"
                    )
                )
                response = self.endpoint.stream_chat_completion(
                    self.model,
                    conversation.get_chat_completion_messages(True),
                    tools=self.tool_descriptions,
                    callback=lambda chunk: self.event_handler(
                        AppendMessageChunkEvent(chunk=chunk)
                    ),
                    system_message=system_msg,
                    **self.additional_model_arguments,
                )
                self.event_handler(ResponseEndEvent(usage=response.usage))
            else:
                response = self.endpoint.chat_completion(
                    self.model,
                    conversation.get_chat_completion_messages(True),
                    tools=self.tool_descriptions,
                    system_message=system_msg,
                    **self.additional_model_arguments,
                )
                self.event_handler(
                    FullResponseEvent(
                        author=self.model_display_name or "Assistant",
                        role="assistant",
                        response=response,
                    )
                )

            if len(response.choices) == 0:
                raise RuntimeError(f"Received empty response: {response}")
            message = response.choices[0].message
            conversation.add_message(
                ConversationMessage(
                    author=self.model_display_name or self.model,
                    message=AssistantMessage(
                        content=message.content, tool_calls=message.tool_calls
                    ),
                )
            )

            # Return when no tools are called
            if message.tool_calls is None:
                return conversation

            # Handle Tool calls
            for tool_call in message.tool_calls:
                self.event_handler(CallToolEvent(call=tool_call))
                with tool.activate_environment(self.tool_environment):
                    if self.allow_shell_executions:
                        with allow_shell_commands():
                            result = _do_tool_call(self.toolbox, tool_call.function)
                    else:
                        result = _do_tool_call(self.toolbox, tool_call.function)

                    self.event_handler(ToolReturnEvent(result=result))
                    conversation.add_message(
                        ConversationMessage.create_tool_response_message(
                            result, tool_call
                        )
                    )
