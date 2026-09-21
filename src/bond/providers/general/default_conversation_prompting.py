from typing import Any, Callable

from returns.result import Failure, Result, Success

from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import AssistantMessage, SystemMessage, TextChunk
from bond.endpoints.chat_completions import (
    ChatCompletionsEndpoint,
    CompletionChunk,
    CompletionResponse,
)
from bond.tools.tool import Tool


class DefaultConversationPromptingStrategy:
    def __init__(
        self,
        model: str,
        model_options: dict[str, Any] | None,
        system_msg: str | None,
        tools: list[Tool],
        max_retries: int,
        author_name: str | None,
        chat_completions: ChatCompletionsEndpoint,
    ):
        self._model = model
        self._model_options = model_options
        self._system_msg = system_msg
        self._tools = tools
        self._max_retries = max_retries
        self._author_name = author_name
        self._chat_completions = chat_completions

    def __call__(
        self,
        conversation: Conversation,
        callback: Callable[[CompletionChunk], None] | None,
    ) -> Result[CompletionResponse, str]:
        can_stream = self._chat_completions.supports_streaming()
        should_stream = callback is not None
        if should_stream and not can_stream:
            return Failure("Streaming is not supported by the provided endpoint")

        try:
            if should_stream:
                response = self._chat_completions.stream_chat_completion(
                    self._model,
                    conversation.get_chat_completion_messages(),
                    self._tools,
                    callback,
                    (
                        SystemMessage(content=[TextChunk(text=self._system_msg)])
                        if self._system_msg is not None
                        else None
                    ),
                    self._model_options,
                    self._max_retries,
                    conversation.metadata,
                )
            else:
                response = self._chat_completions.chat_completion(
                    self._model,
                    conversation.get_chat_completion_messages(),
                    self._tools,
                    (
                        SystemMessage(content=[TextChunk(text=self._system_msg)])
                        if self._system_msg is not None
                        else None
                    ),
                    self._model_options,
                    self._max_retries,
                    conversation.metadata,
                )
            if len(response.choices) == 0:
                return Failure("Received empty response from backend: {response}")
            message = response.choices[0].message
            conversation.add_message(
                ConversationMessage(
                    author=self._author_name or self._model,
                    message=AssistantMessage(
                        content=message.content, tool_calls=message.tool_calls
                    ),
                )
            )
            conversation.current_usage = response.usage.total_tokens
            return Success(response)
        except BaseException as e:
            return Failure(
                f"An exception occured during response generation: {type(e)}: {e}"
            )
