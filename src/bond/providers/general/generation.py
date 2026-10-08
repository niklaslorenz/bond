from typing import Any, Callable

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantMessage,
    ConversationMessage,
    SystemMessage,
    TextChunk,
)
from bond.endpoints.chat_completions import (
    ChatCompletionsEndpoint,
    CompletionChunk,
    CompletionResponse,
)
from bond.tools.tool import Tool


class DefaultGenerationOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    system_prompt: str | None
    pass


class DefaultGenerationCapability:
    def __init__(
        self,
        name: str,
        options: DefaultGenerationOptions,
        tools: list[Tool],
        chat_completions: ChatCompletionsEndpoint,
        max_retries: int,
    ):
        self._name = name
        self._options = options
        self._tools = tools
        self._chat_completions = chat_completions
        self._max_retries = max_retries

    def __call__(
        self,
        conversation: Conversation,
        callback: Callable[[CompletionChunk], None] | None,
    ) -> Result[tuple[CompletionResponse, ConversationMessage], str]:
        can_stream = self._chat_completions.supports_streaming()
        should_stream = callback is not None
        if should_stream and not can_stream:
            return Failure("Streaming is not supported by the provided endpoint")

        system_prompt = self._options.system_prompt
        summary_prompt_extension = (
            (
                "\n<previous-context>\n"
                "  <reliability>imperfect</reliability>\n"
                "  <source>model generated<source>\n"
                "  <content>\n"
                f"    {conversation.summary}\n"
                "  </content>\n"
                "</previous-context>"
            )
            if conversation.summary is not None
            else None
        )
        if system_prompt is not None or summary_prompt_extension is not None:
            system_prompt = (
                (system_prompt or "") + "\n" + (summary_prompt_extension or "")
            )

        try:
            if should_stream:
                response = self._chat_completions.stream_chat_completion(
                    self._options.model,
                    conversation.get_unsummarized_messages(),
                    self._tools,
                    callback,
                    (
                        SystemMessage(content=[TextChunk(text=system_prompt)])
                        if system_prompt is not None
                        else None
                    ),
                    self._options.model_options,
                    self._max_retries,
                    conversation.metadata,
                )
            else:
                response = self._chat_completions.chat_completion(
                    self._options.model,
                    conversation.get_unsummarized_messages(),
                    self._tools,
                    (
                        SystemMessage(
                            content=[TextChunk(text=self._options.system_prompt)]
                        )
                        if self._options.system_prompt is not None
                        else None
                    ),
                    self._options.model_options,
                    self._max_retries,
                    conversation.metadata,
                )
            if len(response.choices) == 0:
                return Failure("Received empty response from backend: {response}")
            message = response.choices[0].message
            conversation_message = ConversationMessage(
                author=self._name,
                message=AssistantMessage(
                    content=message.content, tool_calls=message.tool_calls
                ),
            )
            return Success((response, conversation_message))
        except BaseException as e:
            return Failure(
                f"An exception occured during response generation: {type(e)}: {e}"
            )
