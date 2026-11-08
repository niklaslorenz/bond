from typing import Protocol

from pydantic import BaseModel
from returns.result import Result

from bond.conversation.conversation import Conversation
from bond.conversation.types import (
    AssistantConversationMessage,
    ToolConversationMessage,
    UsageInfo,
    UserConversationMessage,
)
from bond.endpoints.chat_completions import (
    ChatCompletionStreamCallback,
)
from bond.tools.tool import Tool


class GenerationTriggers(BaseModel):
    user_message: UserConversationMessage | None = None
    tool_messages: list[ToolConversationMessage] | None = None


class GenerationCapability(Protocol):
    def generate(
        self,
        conversation: Conversation,
        triggers: GenerationTriggers,
        callback: ChatCompletionStreamCallback | None,
        tools: list[Tool] | None,
    ) -> Result[tuple[AssistantConversationMessage, UsageInfo], str]: ...
