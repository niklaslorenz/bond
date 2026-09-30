from typing import TYPE_CHECKING, Protocol

from returns.result import Result

from bond.conversation.conversation import Conversation, ConversationMessage
from bond.endpoints.chat_completions import (
    ChatCompletionStreamCallback,
    CompletionResponse,
)

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class GenerationCapability(Protocol):
    def __call__(
        self, conversation: Conversation, callback: ChatCompletionStreamCallback | None
    ) -> Result[tuple[CompletionResponse, ConversationMessage], str]: ...
