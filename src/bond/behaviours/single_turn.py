import logging

from returns.result import Success

from bond.bond_environment import BondEnvironment
from bond.conversation import Conversation, ConversationMessage
from bond.endpoints.chat_completions import (AssistantMessage, FunctionCall,
                                             SystemMessage, TextChunk,
                                             ThinkChunk)
from bond.io.io_env import IOEnvironment
from bond.providers.provider import build_toolbox
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
        environment: BondEnvironment,
        persona: str,
        user_name: str = "user",
        io_environment: IOEnvironment | None = None,
        tool_environment: ToolEnvironment | None = None,
        allow_shell_executions: bool = False,
        **additional_chat_completion_arguments,
    ):
        self.environment = environment
        self.persona = environment.get_persona(persona)
        self.user_name = user_name
        self.io_environment = io_environment or IOEnvironment(None, None, None)
        self.tool_environment = tool_environment or ToolEnvironment()
        self.allow_shell_executions = allow_shell_executions
        self.additional_model_arguments = additional_chat_completion_arguments

        self.model = self.persona.model
        self.provider = self.environment.get_provider(self.persona.provider)
        self.system_message = (
            SystemMessage.create(self.persona.system_prompt)
            if self.persona.system_prompt is not None
            else None
        )
        self.toolbox = build_toolbox(
            self.provider,
            [
                tool
                for toolset in self.persona.toolbox
                for tool in self.environment.get_toolset(toolset)
            ],
        )

    def run(self, user_message: str) -> Conversation:
        conversation = Conversation.create(self.persona.name, self.user_name)
        if self.system_message is not None:
            conversation.add_message(
                ConversationMessage(author="System", message=self.system_message)
            )
        conversation.add_message(
            ConversationMessage.create_user_message(user_message, self.user_name)
        )

        while True:
            response = self.provider.chat_completions().chat_completion(
                self.model,
                conversation.get_chat_completion_messages(),
                tools=self.toolbox.get_tool_descriptions(),
                **self.additional_model_arguments,
            )
            message = response.choices[0].message
            conversation.add_message(
                ConversationMessage(
                    author=self.persona.name,
                    message=AssistantMessage(
                        content=message.content, tool_calls=message.tool_calls
                    ),
                )
            )

            # Add text content to the output
            if message.content is not None:
                for chunk in message.content:
                    if isinstance(chunk, TextChunk):
                        if self.io_environment.text_out is not None:
                            self.io_environment.text_out.write(chunk.text + "\n")
                    if isinstance(chunk, ThinkChunk):
                        if self.io_environment.thought_out is not None:
                            for think_chunk in chunk.thinking:
                                if isinstance(think_chunk, TextChunk):
                                    self.io_environment.thought_out.write(
                                        think_chunk.text + "\n"
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
