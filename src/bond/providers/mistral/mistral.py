import os
from typing import Type

from bond.providers.general.summarization import GenericSummarizationEndpoint
from bond.providers.mistral.chat_completions import MistralChatCompletions
from bond.providers.mistral.config import MistralConfig, MistralModelOptions
from bond.providers.mistral.models import MistralModels


class Mistral:
    def __init__(self, config: MistralConfig):
        self.config = config
        self._chat_completions = MistralChatCompletions(self.config)
        self._models = MistralModels(self.config)
        self._summarization = (
            GenericSummarizationEndpoint(self._chat_completions)
            if self.config.summarization is not None
            else None
        )

    def chat_completions(self) -> MistralChatCompletions:
        return self._chat_completions

    def models(self) -> MistralModels:
        return self._models

    def summarization(self) -> GenericSummarizationEndpoint | None:
        return self._summarization

    @classmethod
    def default(cls) -> "Mistral":
        return Mistral(config=MistralConfig(api_key=os.getenv("MISTRAL_API_KEY") or ""))

    @classmethod
    def get_config_type(cls) -> Type[MistralConfig]:
        return MistralConfig

    @classmethod
    def from_config(cls, config: MistralConfig) -> "Mistral":
        return Mistral(config)
