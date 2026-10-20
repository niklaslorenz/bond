import os
from typing import TYPE_CHECKING, Any, Type

from bond.capabilities.generation import GenerationCapability
from bond.providers.general.generation import (
    DefaultGenerationOptions,
)
from bond.providers.general.memory import DefaultMemoryCapability, DefaultMemoryOptions
from bond.providers.general.summarization import DefaultSummarizationOptions
from bond.providers.general.tts import DefaultTTSCapability, DefaultTTSOptions
from bond.providers.general.util import DefaultMessageListBuilder
from bond.providers.mistral.chat_completions import MistralChatCompletions
from bond.providers.mistral.config import MistralConfig
from bond.providers.mistral.embeddings import MistralEmbeddings
from bond.providers.mistral.generation import MistralGeneration
from bond.providers.mistral.models import MistralModels
from bond.providers.mistral.summarization import (
    MistralSummarization,
)
from bond.providers.mistral.tts import MistralTTS
from bond.providers.mistral.voices import MistralVoices
from bond.tools.toolbox import Toolbox

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class Mistral:
    def __init__(self, config: MistralConfig):
        self.config = config
        self._chat_completions = MistralChatCompletions(self.config)
        self._embeddings = MistralEmbeddings(self.config)
        self._models = MistralModels(self.config)
        self._tts = MistralTTS(self.config)
        self._voices = MistralVoices(self.config)
        self._build_message_list = DefaultMessageListBuilder()

    def chat_completions(self) -> MistralChatCompletions:
        return self._chat_completions

    def embeddings(self) -> MistralEmbeddings:
        return self._embeddings

    def models(self) -> MistralModels:
        return self._models

    def voices(self) -> MistralVoices:
        return self._voices

    def tts_endpoint(self) -> MistralTTS:
        return self._tts

    def summarization(
        self,
        config: dict[str, Any],
        generation: GenerationCapability | None = None,
        runtime: "BondRuntime | None" = None,
    ) -> MistralSummarization:
        options = DefaultSummarizationOptions.model_validate(config)
        options.resolve(runtime)
        generation_prompt = generation.system_prompt if generation is not None else None
        return MistralSummarization(
            options,
            self.chat_completions(),
            self._build_message_list,
            generation_prompt,
            (
                str(hash(options.thought_condensation.prompt))
                if options.thought_condensation
                else None
            ),
        )

    def generation(
        self,
        name: str,
        config: dict[str, Any],
        toolbox: Toolbox,
        runtime: "BondRuntime | None" = None,
    ) -> MistralGeneration:
        options = DefaultGenerationOptions.model_validate(config)
        options.resolve(runtime)
        return MistralGeneration(
            name,
            options,
            toolbox.tool_descriptions,
            self.chat_completions(),
            10,
            self._build_message_list,
        )

    def tts(
        self, config: dict[str, Any], runtime: "BondRuntime | None" = None
    ) -> DefaultTTSCapability | None:
        options = DefaultTTSOptions.model_validate(config)
        if options is None:
            return None
        return DefaultTTSCapability(options, self.tts_endpoint(), 10)

    def memory(
        self, config: dict[str, Any], runtime: "BondRuntime | None" = None
    ) -> DefaultMemoryCapability | None:
        options = DefaultMemoryOptions.model_validate(config)
        return DefaultMemoryCapability(options, self.embeddings(), runtime, 10)

    @classmethod
    def default(cls) -> "Mistral":
        return Mistral(config=MistralConfig(api_key=os.getenv("MISTRAL_API_KEY") or ""))

    @classmethod
    def get_config_type(cls) -> Type[MistralConfig]:
        return MistralConfig

    @classmethod
    def from_config(cls, config: MistralConfig) -> "Mistral":
        return Mistral(config)
