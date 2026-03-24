import logging

from returns.result import Success

from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (
    AssistantMessage,
    AssistantMessageChunk,
    FunctionCall,
    TextChunk,
    ThinkChunk,
)
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse
from bond.io.io_env import IOEnvironment
from bond.providers.provider import Provider
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


def _handle_chunk(environment, chunk: AssistantMessageChunk):
    if isinstance(chunk, TextChunk):
        environment.handle_text(chunk.text)
    if isinstance(chunk, ThinkChunk):
        for think_chunk in chunk.thinking:
            if isinstance(think_chunk, TextChunk):
                environment.handle_thought(think_chunk.text)


def _handle_completion_chunk(environment: IOEnvironment, chunk: CompletionChunk):
    if len(chunk.choices) == 0:
        return
    content = chunk.choices[0].delta.content
    if content is not None:
        _handle_chunk(environment, content)


def _handle_response(environment: IOEnvironment, response: CompletionResponse):
    if len(response.choices) == 0:
        return
    message = response.choices[0].message
    if message.content is None:
        return
    for chunk in message.content:
        _handle_chunk(environment, chunk)


class SingleTurn:
    def __init__(
        self,
        provider: Provider,
        model: str,
        toolbox: Toolbox | None = None,
        io_environment: IOEnvironment | None = None,
        tool_environment: ToolEnvironment | None = None,
        model_display_name: str | None = None,
        stream: bool = False,
        allow_shell_executions: bool = False,
        **additional_chat_completion_arguments,
    ):
        self.provider = provider
        self.model = model
        self.toolbox = toolbox if toolbox is not None else Toolbox({})
        self.tool_descriptions = self.toolbox.get_tool_descriptions()
        self.io_environment = io_environment or IOEnvironment(None, None, None)
        self.tool_environment = tool_environment or ToolEnvironment()
        self.model_display_name = model_display_name
        self.stream = stream
        self.allow_shell_executions = allow_shell_executions
        self.additional_model_arguments = additional_chat_completion_arguments

        if stream and not self.provider.chat_completions().supports_streaming():
            raise RuntimeError(
                "The provider does not support streaming for chat completions"
            )

    def run(self, conversation: Conversation) -> Conversation:
        while True:
            if self.stream:
                response = self.provider.chat_completions().stream_chat_completion(
                    self.model,
                    conversation.get_chat_completion_messages(),
                    tools=self.tool_descriptions,
                    callback=lambda chunk: _handle_completion_chunk(
                        self.io_environment, chunk
                    ),
                    **self.additional_model_arguments,
                )
            else:
                response = self.provider.chat_completions().chat_completion(
                    self.model,
                    conversation.get_chat_completion_messages(),
                    tools=self.tool_descriptions,
                    **self.additional_model_arguments,
                )

            if not self.stream:
                _handle_response(self.io_environment, response)
            else:
                self.io_environment.handle_text("\n")
                pass

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
                    conversation.add_message(
                        ConversationMessage.create_tool_response_message(
                            result, tool_call
                        )
                    )
