import logging

from returns.result import Success

from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (AssistantMessage, AssistantMessageChunk,
                                     FunctionCall, TextChunk, ThinkChunk)
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse
from bond.io.agent_output_environment import AgentOutputEnvironment
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


class _OutputHandler:
    _has_unfinished_text: bool = False
    _has_unfinished_thoughts: bool = False

    def __init__(self, environment: AgentOutputEnvironment):
        self._environment = environment

    def start(self):
        self._has_unfinished_text = False
        self._has_unfinished_thoughts = False

    def finalize(self):
        if self._has_unfinished_text:
            self._environment.handle_text("\n")
        if self._has_unfinished_thoughts:
            self._environment.handle_thought("\n")

    def _handle_message_chunk(self, chunk: AssistantMessageChunk):
        if isinstance(chunk, TextChunk) and chunk.text != "":
            self._environment.handle_text(chunk.text)
            self._has_unfinished_text = True
        if isinstance(chunk, ThinkChunk):
            for think_chunk in chunk.thinking:
                if isinstance(think_chunk, TextChunk) and think_chunk.text != "":
                    self._environment.handle_thought(think_chunk.text)
                    self._has_unfinished_thoughts = True

    def handle_completion_chunk(self, chunk: CompletionChunk):
        if len(chunk.choices) == 0:
            return
        content = chunk.choices[0].delta.content
        if content is not None:
            for content_chunk in content:
                self._handle_message_chunk(content_chunk)

    def handle_response(self, response: CompletionResponse):
        if len(response.choices) == 0:
            return
        message = response.choices[0].message
        if message.content is None:
            return
        for chunk in message.content:
            self._handle_message_chunk(chunk)


class SingleTurn:
    def __init__(
        self,
        provider: Provider,
        model: str,
        toolbox: Toolbox | None = None,
        aoe: AgentOutputEnvironment | None = None,
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
        self.aoe = aoe or AgentOutputEnvironment(None, None)
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
        output_handler = _OutputHandler(self.aoe)
        while True:
            output_handler.start()
            if self.stream:
                response = self.provider.chat_completions().stream_chat_completion(
                    self.model,
                    conversation.get_chat_completion_messages(),
                    tools=self.tool_descriptions,
                    callback=lambda chunk: output_handler.handle_completion_chunk(
                        chunk
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
                output_handler.handle_response(response)
            output_handler.finalize()

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
                    conversation.add_message(
                        ConversationMessage.create_tool_response_message(
                            result, tool_call
                        )
                    )
