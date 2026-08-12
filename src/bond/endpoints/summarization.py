from typing import Protocol

from pydantic import BaseModel

from bond.conversation.types import Message
from bond.endpoints.chat_completions import CompletionResponse


class SummarizationOptions[ModelOptions: BaseModel](BaseModel):
    model: str
    """The model to use for summarization"""
    keep: int
    """The number of last messages to not summarize and keep as is"""
    token_threshold: int | None = None
    """The total number of tokens in the last completion that will trigger a summarization"""
    min_unsummarized_messages: int
    """The minumum number of unsummarized messages that need to exist before a summarization is triggered (takes precedence over token_threshold)"""
    max_unsummarized_messages: int
    """The maximum number of unsummarized messages that can exist before a summarization is triggered (takes precedence over min_summarized_messages)"""
    prompt: str
    """System prompt that is used for the summarization task"""
    model_options: ModelOptions | None = None
    """Other model options for the summarization"""


class SummarizationEndpoint[ModelOptions: BaseModel](Protocol):

    def get_options(self) -> SummarizationOptions: ...

    def summarize(
        self,
        messages: list[Message],
        max_retries: int = 10,
    ) -> CompletionResponse: ...
