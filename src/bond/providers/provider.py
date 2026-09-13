from typing import Protocol, Self, Type

from pydantic import BaseModel
from returns.result import Result

from bond.conversation.conversation import Conversation
from bond.endpoints.chat_completions import (
    ChatCompletionsEndpoint,
    ChatCompletionStreamCallback,
    CompletionResponse,
)
from bond.endpoints.models import ModelsEndpoint
from bond.persona import Persona
from bond.tools.toolbox import Toolbox


class ConversationPromptingStrategy(Protocol):
    def __call__(
        self, conversation: Conversation, callback: ChatCompletionStreamCallback | None
    ) -> Result[CompletionResponse, str]: ...


class ConversationSummarizationStrategy(Protocol):
    def __call__(
        self, conversation: Conversation
    ) -> Result[CompletionResponse, str]: ...


class Provider[ConfigType: BaseModel](Protocol):
    @classmethod
    def get_config_type(cls) -> Type[ConfigType]: ...
    @classmethod
    def from_config(cls, config: ConfigType) -> Self: ...

    def models(self) -> ModelsEndpoint: ...
    def chat_completions(self) -> ChatCompletionsEndpoint: ...

    def conversation_summarization(
        self,
        persona: Persona,
    ) -> ConversationSummarizationStrategy | None: ...
    def conversation_prompting(
        self,
        persona: Persona,
        toolbox: Toolbox,
    ) -> ConversationPromptingStrategy | None: ...
