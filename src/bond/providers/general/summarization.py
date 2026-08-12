from pydantic import BaseModel

from bond.conversation.conversation import Conversation
from bond.conversation.types import Message, SystemMessage, TextChunk
from bond.endpoints.chat_completions import ChatCompletionsEndpoint, CompletionResponse
from bond.endpoints.summarization import SummarizationOptions


class GenericSummarizationEndpoint[ModelOptions: BaseModel]:
    def __init__(
        self,
        chat_completions: ChatCompletionsEndpoint[ModelOptions],
        summarization_options: SummarizationOptions[ModelOptions],
    ):
        self.chat_completions = chat_completions
        self.summarization_options = summarization_options

    def get_options(self) -> SummarizationOptions[ModelOptions]:
        return self.summarization_options

    def summarize(
        self,
        messages: list[Message],
        max_retries: int = 10,
    ) -> CompletionResponse:
        filtered_messages: list[Message] = [
            msg for msg in messages if msg.role != "system"
        ]
        return self.chat_completions.chat_completion(
            self.summarization_options.model,
            filtered_messages,
            [],
            SystemMessage(content=[TextChunk(text=self.summarization_options.prompt)]),
            self.summarization_options.model_options,
            max_retries,
        )
