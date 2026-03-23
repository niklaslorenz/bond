from pathlib import Path
from typing import Annotated, Protocol, Union

from pydantic import Field, TypeAdapter

from bond.endpoints.chat_completions import ChatCompletionsEndpoint, Tool
from bond.endpoints.model_options import ModelOptions
from bond.endpoints.models import ModelsEndpoint
from bond.providers.mistral.mistral import Mistral, MistralConfig
from bond.providers.ollama import OllamaConfig
from bond.providers.openai import OpenAIConfig
from bond.tools.tool import Toolbox, ToolFn

ProviderConfig = Annotated[
    Union[MistralConfig, OpenAIConfig, OllamaConfig], Field(discriminator="type")
]
_config_adapter = TypeAdapter(ProviderConfig)


def load_config_from(path: Path) -> ProviderConfig:
    if not path.exists():
        raise ValueError(f"Invalid path: {path}")
    if path.suffix != ".json":
        raise ValueError(f"Invalid file extension: {path.suffix}. Must be .json")
    return _config_adapter.validate_json(path.read_text())


class Provider[ModelArgumentType: ModelOptions](Protocol):
    def models(self) -> ModelsEndpoint: ...
    def chat_completions(self) -> ChatCompletionsEndpoint[ModelArgumentType]: ...
    def parse_tool(self, tool: ToolFn) -> tuple[str, Tool]: ...


def build_toolbox(provider: Provider, tools: list[ToolFn]) -> Toolbox:
    parsed_tools = [(provider.parse_tool(tool), tool) for tool in tools]
    return Toolbox({name: (tool, desc) for (name, desc), tool in parsed_tools})


def construct_provider(config: ProviderConfig) -> Provider:
    if isinstance(config, MistralConfig):
        return Mistral(config)
    if isinstance(config, OllamaConfig):
        return config.construct()
    else:
        raise NotImplementedError()
