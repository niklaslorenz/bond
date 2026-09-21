from typing import Any

from returns.result import Failure, Result, Success

from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, TextChunk, UserMessage
from bond.endpoints.chat_completions import ChatCompletionsEndpoint, CompletionResponse

from . import logger


class MistralConversationSummarizationStrategy:
    def __init__(
        self,
        model: str,
        model_options: dict[str, Any] | None,
        summarization_instruction: str,
        keep: int,
        max_retries: int,
        chat_completions: ChatCompletionsEndpoint,
    ):
        self._model = model
        self._model_options = model_options
        self._summarization_instruction = summarization_instruction
        self._keep = keep
        self._max_retries = max_retries
        self._chat_completions = chat_completions

    def __call__(self, conversation: Conversation) -> Result[CompletionResponse, str]:
        logger.debug("Preparing summarization")
        messages, n_kept = self._extract_message_list(conversation)
        if len(messages) == 0:
            return Failure(f"Summarization triggered with no messages to summarize")
        logger.debug(f"Summarizing {len(messages)} messages")

        messages.append(
            UserMessage(content=[TextChunk(text=self._summarization_instruction)])
        )

        try:
            response = self._chat_completions.chat_completion(
                self._model,
                messages,
                [],
                None,
                self._model_options,
                self._max_retries,
            )
        except BaseException as e:
            return Failure(f"An error occured while creating summary ({type(e)}): {e}")

        summary_msg = response.choices[0].message
        if summary_msg.tool_calls:
            logger.warning(
                "Summary call returned with tool calls. This is not expected and the tool calls will be discarded."
            )
        if summary_msg.content is None:
            logger.warning("Failed to create summary: no content")
            return Failure("Summary call returned without content")
        logger.debug(f"successfully created summary")

        summary = "".join(
            chunk.text for chunk in summary_msg.content if isinstance(chunk, TextChunk)
        )
        conversation.update_summary(summary, n_kept)
        logger.debug("Updated summary")
        return Success(response)

    def _extract_message_list(
        self, conversation: Conversation
    ) -> tuple[list[Message], int]:
        # TODO: make sure messages is a valid list. Maybe not use get_summary_messages
        # "valid" in this case means adhering to the mistral message list specification
        messages = conversation.get_summary_messages(self._keep)
        return messages, self._keep
