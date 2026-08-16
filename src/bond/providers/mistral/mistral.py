import os
from typing import Type

import smolagents.tools

from bond.providers.mistral.chat_completions import MistralChatCompletions
from bond.providers.mistral.config import MistralConfig
from bond.providers.mistral.models import MistralModels
from bond.tools.tool import Tool, ToolFn


class Mistral:
    def __init__(self, config: MistralConfig):
        self.config = config
        self._chat_completions = MistralChatCompletions(self.config)
        self._models = MistralModels(self.config)

    def chat_completions(self) -> MistralChatCompletions:
        return self._chat_completions

    def models(self) -> MistralModels:
        return self._models

    def parse_tool(self, tool: ToolFn) -> tuple[str, Tool]:
        desc = smolagents.tools.get_json_schema(tool)
        parsed = Tool.model_validate(desc)
        return parsed.function.name, parsed

    @classmethod
    def default(cls) -> "Mistral":
        return Mistral(config=MistralConfig(api_key=os.getenv("MISTRAL_API_KEY") or ""))

    @classmethod
    def get_config_type(cls) -> Type[MistralConfig]:
        return MistralConfig

    @classmethod
    def from_config(cls, config: MistralConfig) -> "Mistral":
        return Mistral(config)
