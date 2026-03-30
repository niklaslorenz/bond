import logging

from returns.result import Success

from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (AssistantMessage, FunctionCall,
                                     SystemMessage)
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.io.io import AgentOutputEnvironment
from bond.tools.shell import allow_shell_commands
from bond.tools.tool import Toolbox, ToolEnvironment

logger = logging.getLogger(__name__)


def _do_tool_call(toolbox: Toolbox, function_call: FunctionCall) -> str:
    result = toolbox.call_tool(function_call.name, function_call.arguments)
    logger.info(f"Tool call returned object of type {type(result)}:\n{result}")
    if isinstance(result, Success):
        return result.unwrap()
    else:
        return f"An error occured before the tool execution: {result.failure()}"


class SingleTurn:
    def __init__(
        self,
        endpoint: ChatCompletionsEndpoint,
        model: str,
        aoe: AgentOutputEnvironment,
        system_message: str | None = None,
        toolbox: Toolbox | None = None,
        tool_environment: ToolEnvironment | None = None,
        model_display_name: str | None = None,
        stream: bool = False,
        allow_shell_executions: bool = False,
        **additional_chat_completion_arguments,
    ):
        self.endpoint = endpoint
        self.model = model
        self.aoe = aoe
        self.system_message = system_message
        self.toolbox = toolbox if toolbox is not None else Toolbox({})
        self.tool_descriptions = self.toolbox.get_tool_descriptions()
        self.tool_environment = tool_environment or ToolEnvironment()
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
            system_msg = (
                SystemMessage.create(self.system_message)
                if self.system_message is not None
                else None
            )
            if self.stream:
                self.aoe.start_streaming_response(self.model_display_name)
                response = self.endpoint.stream_chat_completion(
                    self.model,
                    conversation.get_chat_completion_messages(True),
                    tools=self.tool_descriptions,
                    callback=self.aoe.handle_response_chunk,
                    system_message=system_msg,
                    **self.additional_model_arguments,
                )
                self.aoe.end_streaming_response(response.usage)
            else:
                response = self.endpoint.chat_completion(
                    self.model,
                    conversation.get_chat_completion_messages(True),
                    tools=self.tool_descriptions,
                    system_message=system_msg,
                    **self.additional_model_arguments,
                )
                self.aoe.handle_response(response)

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
                with self.tool_environment.activate():
                    if self.allow_shell_executions:
                        with allow_shell_commands():
                            result = _do_tool_call(self.toolbox, tool_call.function)
                    else:
                        result = _do_tool_call(self.toolbox, tool_call.function)
                    self.aoe.handle_tool_result(tool_call, result)
                    conversation.add_message(
                        ConversationMessage.create_tool_response_message(
                            result, tool_call
                        )
                    )
