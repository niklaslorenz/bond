from typing import Protocol, Self, Type


from bond.endpoints.chat_completions import ChatCompletionsEndpoint
from pydantic import BaseModel, Field, TypeAdapter
from bond.endpoints.models import ModelsEndpoint


class Provider[ConfigType: BaseModel, ModelOptions: BaseModel](Protocol):
    @classmethod
    def get_config_type(cls) -> Type[ConfigType]: ...
    @classmethod
    def from_config(cls, config: ConfigType) -> Self: ...
    def models(self) -> ModelsEndpoint: ...
    def chat_completions(self) -> ChatCompletionsEndpoint[ModelArgumentType]: ...

