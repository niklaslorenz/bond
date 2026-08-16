from typing import Protocol, Self, Type

from pydantic import BaseModel

from bond.endpoints.chat_completions import ChatCompletionsEndpoint, Tool
from bond.endpoints.model_options import ModelOptions
from bond.endpoints.models import ModelsEndpoint
from bond.tools.tool import ToolFn


class Provider[ConfigType: BaseModel, ModelArgumentType: ModelOptions](Protocol):
    @classmethod
    def get_config_type(cls) -> Type[ConfigType]: ...
    @classmethod
    def from_config(cls, config: ConfigType) -> Self: ...
    def models(self) -> ModelsEndpoint: ...
    def chat_completions(self) -> ChatCompletionsEndpoint[ModelArgumentType]: ...
    def parse_tool(self, tool: ToolFn) -> tuple[str, Tool]: ...
