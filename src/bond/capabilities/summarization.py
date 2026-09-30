from typing import Protocol

from pydantic import BaseModel
from returns.result import Result

from bond.conversation.conversation import Conversation


class AutoSummarizationOptions(BaseModel):
    token_threshold: int | None = None
    """Number of input and output tokens that triggers an automatic summarization at the end ot the turn."""
    min_messages: int = 10
    """Minimum number of messages required to trigger an automatic summarization. Takes precedence over token_threshold"""
    max_messages: int = 30
    """Maximum number of messages before triggering an automatic summarization. Takes precedence over token_threshold"""


class SummarizationCapability(Protocol):
    def __call__(self, conversation: Conversation) -> Result[str, str]: ...

    def auto_summarization_options(self) -> AutoSummarizationOptions | None: ...
