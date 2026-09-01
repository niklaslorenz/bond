from typing import Any, Protocol

from bond.conversation.types import (ConversationMetadata, Message,
                                     SystemMessage)
from bond.endpoints.chat_completions import CompletionResponse


class SummarizationEndpoint(Protocol):

    def summarize(
        self,
        model: str,
        messages: list[Message],
        system_message: SystemMessage | None = None,
        options: dict[str, Any] | None = None,
        max_retries: int = 10,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse: ...
