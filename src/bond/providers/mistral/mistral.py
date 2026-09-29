import os
from typing import Type

from bond.persona import Persona
from bond.providers.general.default_conversation_prompting import (
    DefaultConversationPromptingStrategy,
)
from bond.providers.general.default_tts_strategy import DefaultTTSStrategy
from bond.providers.mistral.chat_completions import MistralChatCompletions
from bond.providers.mistral.config import MistralConfig
from bond.providers.mistral.conversation_summary import (
    MistralConversationSummarizationStrategy,
)
from bond.providers.mistral.models import MistralModels
from bond.providers.mistral.tts import MistralTTS
from bond.providers.mistral.voices import MistralVoices
from bond.tools.toolbox import Toolbox


class Mistral:
    def __init__(self, config: MistralConfig):
        self.config = config
        self._chat_completions = MistralChatCompletions(self.config)
        self._models = MistralModels(self.config)
        self._tts = MistralTTS(self.config)
        self._voices = MistralVoices(self.config)

    def chat_completions(self) -> MistralChatCompletions:
        return self._chat_completions

    def models(self) -> MistralModels:
        return self._models

    def voices(self) -> MistralVoices:
        return self._voices

    def tts(self) -> MistralTTS:
        return self._tts

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
            persona.system_prompt,
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
            toolbox.tool_descriptions,
            10,
            persona.name,
            self.chat_completions(),
        )

    def tts_strategy(self, persona: Persona) -> DefaultTTSStrategy | None:
        opts = persona.tts
        if opts is None:
            return None
        if opts.voice is None:
            raise ValueError("Mistral tts requires the voice parameter")
        return DefaultTTSStrategy(self._tts, opts.model, opts.voice)

    @classmethod
    def default(cls) -> "Mistral":
        return Mistral(config=MistralConfig(api_key=os.getenv("MISTRAL_API_KEY") or ""))

    @classmethod
    def get_config_type(cls) -> Type[MistralConfig]:
        return MistralConfig

    @classmethod
    def from_config(cls, config: MistralConfig) -> "Mistral":
        return Mistral(config)
