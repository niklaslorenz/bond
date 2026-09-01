from typing import Any

from bond.conversation.types import (ConversationMetadata, Message,
                                     SystemMessage, TextChunk)
from bond.endpoints.chat_completions import (ChatCompletionsEndpoint,
                                             CompletionResponse)
from bond.persona import SummarizationOptions

from .. import logger


class GenericSummarizationEndpoint:
    def __init__(
        self,
        chat_completions: ChatCompletionsEndpoint,
    ):
        self.chat_completions = chat_completions

    def summarize(
        self,
        model: str,
        messages: list[Message],
        system_message: SystemMessage | None = None,
        options: dict[str, Any] | None = None,
        max_retries: int = 10,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse:
        filtered_messages: list[Message] = [
            msg for msg in messages if msg.role != "system"
        ]
        logger.debug(f"Summarizing {len(messages)} messages")
        response = self.chat_completions.chat_completion(
            model,
            filtered_messages,
            [],
            system_message,
            options,
            max_retries,
        )
        logger.debug(f"successfully created summary")
        return response
