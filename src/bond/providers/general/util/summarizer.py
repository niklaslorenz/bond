import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.capabilities.types import MessageListBuilder, SystemMessageBuilder
from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, SystemMessage, TextChunk, UserMessage
from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.providers.general.util.markdown_renderer import MarkdownRenderer

logger = logging.getLogger(__name__)


class Summarizer(ABC):
    @abstractmethod
    def run(
        self, conversation: Conversation, turns: int | None
    ) -> Result[str, str]: ...


class ChunkRenderedSummarizerOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    chunk_size: int


class ChunkRenderedSummarizer(Summarizer):
    pass


class MessageListBulkSummarizerOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    instruction: str


class MessageListBulkSummarizer(Summarizer):

    def __init__(
        self,
        options: MessageListBulkSummarizerOptions,
        chat_completions: ChatCompletionsEndpoint,
        system_message_builder: SystemMessageBuilder,
        message_list_builder: MessageListBuilder,
    ):
        self._options = options
        self._chat_completions = chat_completions
        self._system_message_builder = system_message_builder
        self._message_list_builder = message_list_builder

    def run(self, conversation: Conversation, turns: int | None) -> Result[str, str]:
        options = self._options

        message_list = self._message_list_builder.render_conversation(
            conversation, turns
        )
        system_msg = self._system_message_builder.render_system_message(
            conversation, options.prompt
        )
        instruction_msg = UserMessage(content=[TextChunk(text=options.instruction)])
        message_list.append(instruction_msg)
        response = self._chat_completions.chat_completion(
            options.model,
            message_list,
            [],
            system_msg,
            options.model_options,
        )
        if response.choices[0].message.tool_calls is not None:
            logger.warning(
                "Episode summarization call generated tool calls which is unexpected.\n"
                + "\n".join(
                    f"Function: {tool_call.function.name}\nParameters: {tool_call.function.arguments}"
                    for tool_call in response.choices[0].message.tool_calls
                )
            )
        if (content := response.choices[0].message.content) is None:
            return Failure("Model returned with no content")
        summary = "".join(
            [chunk.text for chunk in content if isinstance(chunk, TextChunk)]
        )
        if summary == "":
            return Failure("Model returned with no content")
        return Success(summary)


class MarkdownBulkSummarizerOptions(BaseModel):
    model: str
    model_options: dict[str, Any] | None = None
    prompt: str
    instruction: str


class MarkdownBulkSummarizer(Summarizer):
    def __init__(
        self,
        options: MarkdownBulkSummarizerOptions,
        chat_completions: ChatCompletionsEndpoint,
    ):
        self._options = options
        self._chat_completions = chat_completions

    def run(self, conversation: Conversation, turns: int | None) -> Result[str, str]:
        options = self._options
        renderer = MarkdownRenderer()
        rendered = renderer.render_conversation(conversation, turns)

        system_message = SystemMessage(content=[TextChunk(text=options.prompt)])
        message_list: list[Message] = [
            UserMessage(content=[TextChunk(text=rendered)]),
        ]

        response = self._chat_completions.chat_completion(
            options.model, message_list, [], system_message, options.model_options
        )
        if response.choices[0].message.tool_calls is not None:
            logger.warning(
                "Episode summarization call generated tool calls which is unexpected.\n"
                + "\n".join(
                    f"Function: {tool_call.function.name}\nParameters: {tool_call.function.arguments}"
                    for tool_call in response.choices[0].message.tool_calls
                )
            )
        if (content := response.choices[0].message.content) is None:
            return Failure("Model returned with no content")
        summary = "".join(
            [chunk.text for chunk in content if isinstance(chunk, TextChunk)]
        )
        if summary == "":
            return Failure("Model returned with no content")
        return Success(summary)
