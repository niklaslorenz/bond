from pathlib import Path
from typing import Annotated, Any, Protocol, Union

from pydantic import Field, TypeAdapter

from bond.endpoints.chat_completions import ChatCompletionsWrapper
from bond.endpoints.model_options import ModelOptions
from bond.endpoints.models import ModelsWrapper
from bond.providers.mistral import MistralConfig
from bond.providers.ollama import OllamaConfig
from bond.providers.openai import OpenAIConfig
from bond.tools.tool import Tool, Toolbox

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
    def models(self) -> ModelsWrapper: ...
    def chat_completions(self) -> ChatCompletionsWrapper[ModelArgumentType]: ...
    def parse_tool(self, tool: Tool) -> tuple[str, dict[str, Any]]: ...


def build_toolbox(provider: Provider, tools: list[Tool]) -> Toolbox:
    parsed_tools = [(provider.parse_tool(tool), tool) for tool in tools]
    return Toolbox({name: (tool, desc) for (name, desc), tool in parsed_tools})


def construct_provider(config: ProviderConfig) -> Provider:
    if isinstance(config, MistralConfig) or isinstance(config, OllamaConfig):
        return config.construct()
    else:
        raise NotImplementedError()
