from typing import Literal

from pydantic import BaseModel

from bond.providers.mistral.chat_completions import (
    MistralChatCompletionOptions, MistralChatCompletions)


class MistralConfig(BaseModel):
    type: Literal["mistral"] = "mistral"
    api_key: str
    models: list[str] | None = None
    chat_completion_options: MistralChatCompletionOptions | None = None
    model_specific_chat_completion_options: (
        dict[str, MistralChatCompletionOptions] | None
    ) = None

    def construct(self) -> "Mistral":
        return Mistral(self)


class Mistral:
    def __init__(self, config: MistralConfig):
        self.config = config
        self._chat_completions = MistralChatCompletions(self.config)

    def chat_completions(self) -> MistralChatCompletions:
        return self._chat_completions
