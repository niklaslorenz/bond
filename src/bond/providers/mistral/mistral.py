import os
from typing import Type

from bond.persona import Persona
from bond.providers.general.default_conversation_prompting import (
    DefaultConversationPromptingStrategy,
)
from bond.providers.mistral.chat_completions import MistralChatCompletions
from bond.providers.mistral.config import MistralConfig
from bond.providers.mistral.conversation_summary import (
    MistralConversationSummarizationStrategy,
)
from bond.providers.mistral.models import MistralModels
from bond.tools.toolbox import Toolbox


class Mistral:
    def __init__(self, config: MistralConfig):
        self.config = config
        self._chat_completions = MistralChatCompletions(self.config)
        self._models = MistralModels(self.config)

    def chat_completions(self) -> MistralChatCompletions:
        return self._chat_completions

    def models(self) -> MistralModels:
        return self._models

    def conversation_summarization(
        self, persona: Persona
    ) -> MistralConversationSummarizationStrategy | None:
        if persona.summarization is None:
            return None
        options = persona.summarization
        return MistralConversationSummarizationStrategy(
            options.model or persona.model,
            options.model_options,
            options.instruction,
            options.keep,
            10,
            self.chat_completions(),
        )

    def conversation_prompting(
        self,
        persona: Persona,
        toolbox: Toolbox,
    ) -> DefaultConversationPromptingStrategy:
        assert persona.provider == "mistral"
        return DefaultConversationPromptingStrategy(
            persona.model,
            persona.model_options,
            persona.system_prompt,
            toolbox.get_tool_descriptions(),
            10,
            persona.name,
            self.chat_completions(),
        )

    @classmethod
    def default(cls) -> "Mistral":
        return Mistral(config=MistralConfig(api_key=os.getenv("MISTRAL_API_KEY") or ""))

    @classmethod
    def get_config_type(cls) -> Type[MistralConfig]:
        return MistralConfig

    @classmethod
    def from_config(cls, config: MistralConfig) -> "Mistral":
        return Mistral(config)
