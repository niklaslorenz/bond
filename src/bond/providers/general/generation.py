from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.capabilities.generation import GenerationTriggers
from bond.capabilities.types import MessageListBuilder, SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    UsageInfo,
    UserConversationMessage,
)
from bond.endpoints.chat_completions import (
    ChatCompletionsEndpoint,
    CompletionChunk,
)
from bond.tools.tool import Tool
from bond.util import resolve_skills

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class DefaultGenerationOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    system_prompt: str | None

    def resolve(self, runtime: "BondRuntime | None"):
        if self.system_prompt is not None:
            self.system_prompt = resolve_skills(self.system_prompt, runtime)


class DefaultGenerationCapability:
    def __init__(
        self,
        name: str,
        options: DefaultGenerationOptions,
        tools: list[Tool],
        chat_completions: ChatCompletionsEndpoint,
        max_retries: int,
        system_message_builder: SystemMessageBuilder,
        message_list_builder: MessageListBuilder,
    ):
        self._name = name
        self._options = options
        self._tools = tools
        self._chat_completions = chat_completions
        self._max_retries = max_retries
        self._system_message_builder = system_message_builder
        self._message_list_builder = message_list_builder

    def generate(
        self,
        conversation: Conversation,
        triggers: GenerationTriggers,
        callback: Callable[[CompletionChunk], None] | None,
        model_options: dict[str, Any] | None = None,
    ) -> Result[tuple[AssistantConversationMessage, UsageInfo], str]:
        can_stream = self._chat_completions.supports_streaming()
        should_stream = callback is not None
        if should_stream and not can_stream:
            return Failure("Streaming is not supported by the provided endpoint")

        system_message = self._system_message_builder.render_system_message(
            conversation, self._options.system_prompt
        )
        messages = self._message_list_builder.render_conversation(conversation)

        if triggers.tool_messages is not None:
            messages.extend(
                sum(
                    (
                        self._message_list_builder.render_tool_message(tool_msg)
                        for tool_msg in triggers.tool_messages
                    ),
                    [],
                )
            )
        if triggers.user_message is not None:
            messages.extend(
                self._message_list_builder.render_user_message(triggers.user_message)
            )

        all_model_options: dict[str, Any] = {
            **(self._options.model_options or {}),
            **(model_options or {}),
        }

        # Generate response
        try:
            if should_stream:
                response = self._chat_completions.stream_chat_completion(
                    self._options.model,
                    messages,
                    self._tools,
                    callback,
                    system_message,
                    all_model_options,
                    self._max_retries,
                )
            else:
                response = self._chat_completions.chat_completion(
                    self._options.model,
                    messages,
                    self._tools,
                    system_message,
                    all_model_options,
                    self._max_retries,
                )
            if len(response.choices) == 0:
                return Failure(f"Received empty response from backend: {response}")
            message = response.choices[0].message
            conversation_message = AssistantConversationMessage(
                name=self._name,
                message=message,
            )
            return Success((conversation_message, response.usage))
        except BaseException as e:
            return Failure(
                f"An exception occured during response generation: {type(e)}: {e}"
            )

    @property
    def system_prompt(self) -> str | None:
        return self._options.system_prompt
