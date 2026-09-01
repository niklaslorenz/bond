from typing import Protocol, Self, Type

from pydantic import BaseModel

from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from bond.endpoints.models import ModelsEndpoint
from bond.endpoints.summarization import SummarizationEndpoint


class Provider[ConfigType: BaseModel](Protocol):
    @classmethod
    def get_config_type(cls) -> Type[ConfigType]: ...
    @classmethod
    def from_config(cls, config: ConfigType) -> Self: ...
    def models(self) -> ModelsEndpoint: ...
    def chat_completions(self) -> ChatCompletionsEndpoint: ...
    def summarization(self) -> SummarizationEndpoint | None: ...
