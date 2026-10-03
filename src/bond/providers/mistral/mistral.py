import os
from typing import TYPE_CHECKING, Any, Type

from bond.providers.general.generation import (
    DefaultGenerationCapability,
    DefaultGenerationOptions,
)
from bond.providers.general.tts import DefaultTTSCapability, DefaultTTSOptions
from bond.providers.mistral.chat_completions import MistralChatCompletions
from bond.providers.mistral.config import MistralConfig
from bond.providers.mistral.models import MistralModels
from bond.providers.mistral.summarization import (
    MistralSummarization,
    MistralSummarizationOptions,
)
from bond.providers.mistral.tts import MistralTTS
from bond.providers.mistral.voices import MistralVoices
from bond.tools.toolbox import Toolbox
from bond.util import resolve_skills

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


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

    def tts_endpoint(self) -> MistralTTS:
        return self._tts

    def summarization(
        self, config: dict[str, Any], runtime: "BondRuntime | None" = None
    ) -> MistralSummarization:
        options = MistralSummarizationOptions.model_validate(config)
        options.instruction = resolve_skills(options.instruction, runtime)
        options.system_prompt = resolve_skills(options.system_prompt, runtime)
        return MistralSummarization(
            options,
            self.chat_completions(),
            10,
        )

    def generation(
        self,
        name: str,
        config: dict[str, Any],
        toolbox: Toolbox,
        runtime: "BondRuntime | None" = None,
    ) -> DefaultGenerationCapability:
        options = DefaultGenerationOptions.model_validate(config)
        options.system_prompt = resolve_skills(options.system_prompt, runtime)
        return DefaultGenerationCapability(
            name, options, toolbox.tool_descriptions, self.chat_completions(), 10
        )

    def tts(
        self, config: dict[str, Any], runtime: "BondRuntime | None" = None
    ) -> DefaultTTSCapability | None:
        options = DefaultTTSOptions.model_validate(config)
        if options is None:
            return None
        return DefaultTTSCapability(options, self.tts_endpoint(), 10)

    @classmethod
    def default(cls) -> "Mistral":
        return Mistral(config=MistralConfig(api_key=os.getenv("MISTRAL_API_KEY") or ""))

    @classmethod
    def get_config_type(cls) -> Type[MistralConfig]:
        return MistralConfig

    @classmethod
    def from_config(cls, config: MistralConfig) -> "Mistral":
        return Mistral(config)
