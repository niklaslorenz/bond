import os
from typing import Any, Literal
from urllib.parse import urljoin

import requests
from pydantic import BaseModel
from smolagents.tools import get_json_schema

from bond.endpoints.chat_completions import ChatCompletionsWrapper, Message
from bond.endpoints.model_options import ModelOptions
from bond.endpoints.models import ModelsWrapper
from bond.tools.tool import Tool
from bond.util import resolve_api_key


class MistralAPI:
    def __init__(self, api_key: str):
        self.base_url = "https://api.mistral.ai/v1/"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **additional_fields,
    ) -> requests.Response:
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in messages],
            "tools": tools,
            **additional_fields,
        }
        response = requests.post(
            urljoin(self.base_url, "chat/completions"),
            headers=self.headers,
            json=payload,
        )
        return response

    def retrieve_model(self, id: str) -> requests.Response:
        response = requests.get(
            urljoin(self.base_url, f"models/{id}"), headers=self.headers
        )
        return response

    def list_models(self) -> requests.Response:
        response = requests.get(urljoin(self.base_url, "models"), headers=self.headers)
        return response

    @classmethod
    def create(cls, api_key: str | None = None) -> "MistralAPI":
        return MistralAPI(
            api_key=(
                api_key if api_key is not None else os.getenv("MISTRAL_API_KEY") or ""
            )
        )


class MistralChatCompletionOptions(ModelOptions):
    temperature: float = 0.7


class Mistral:
    def __init__(self, api_key: str | None = None):
        self.api = MistralAPI.create(api_key)
        self._models = ModelsWrapper(self.api)
        self._chat_completions = ChatCompletionsWrapper[MistralChatCompletionOptions](
            self.api, arguments_type=MistralChatCompletionOptions
        )

    def models(self) -> ModelsWrapper:
        return self._models

    def chat_completions(self) -> ChatCompletionsWrapper[MistralChatCompletionOptions]:
        return self._chat_completions

    def parse_tool(self, tool: Tool) -> tuple[str, dict[str, Any]]:
        raw = get_json_schema(tool)
        if "return" in raw["function"]:
            raw["function"].pop("return")
        return raw["function"]["name"], raw


class MistralConfig(BaseModel):
    type: Literal["mistral"] = "mistral"
    api_key: str
    models: list[str] | None = None
    chat_completion_options: MistralChatCompletionOptions | None = None
    model_specific_chat_completion_options: (
        dict[str, MistralChatCompletionOptions] | None
    ) = None

    def construct(self) -> Mistral:
        return Mistral(resolve_api_key(self.api_key))
