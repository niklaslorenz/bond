from typing import TYPE_CHECKING, Any, Protocol, Self, Type

from pydantic import BaseModel

from bond.capabilities.generation import GenerationCapability
from bond.capabilities.summarization import SummarizationCapability
from bond.capabilities.tts import TTSCapability
from bond.endpoints.chat_completions import (
    ChatCompletionsEndpoint,
)
from bond.endpoints.models import ModelsEndpoint
from bond.endpoints.tts import TTSEndpoint
from bond.endpoints.voices import VoicesEndpoint
from bond.tools.toolbox import Toolbox

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class Provider[ConfigType: BaseModel](Protocol):
    @classmethod
    def get_config_type(cls) -> Type[ConfigType]: ...
    @classmethod
    def from_config(cls, config: ConfigType) -> Self: ...

    def chat_completions(self) -> ChatCompletionsEndpoint | None: ...
    def models(self) -> ModelsEndpoint | None: ...
    def tts_endpoint(self) -> TTSEndpoint | None: ...
    def voices(self) -> VoicesEndpoint | None: ...

    def generation(
        self,
        name: str,
        config: dict[str, Any],
        toolbox: Toolbox,
        runtime: "BondRuntime | None" = None,
    ) -> "GenerationCapability | None": ...
    def summarization(
        self, config: dict[str, Any], runtime: "BondRuntime | None" = None
    ) -> "SummarizationCapability | None": ...
    def tts(
        self, config: dict[str, Any], runtime: "BondRuntime | None" = None
    ) -> "TTSCapability | None": ...
