import os

import requests

from bond.endpoints.chat_completions import ChatCompletionsWrapper, Message
from bond.endpoints.models import ModelsWrapper


class MistralAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1/"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **additional_fields,
    ) -> requests.Response:
        payload = {
            "model": model,
            "messages": [msg.model_dump() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **additional_fields,
        }
        response = requests.post(
            f"{self.base_url}chat/completions", headers=self.headers, json=payload
        )
        return response

    def retrieve_model(self, id: str) -> requests.Response:
        response = requests.get(f"{self.base_url}models/{id}", headers=self.headers)
        return response

    def list_models(self) -> requests.Response:
        response = requests.get(f"{self.base_url}models", headers=self.headers)
        return response

    @classmethod
    def create(cls, api_key: str | None = None) -> "MistralAPI":
        return MistralAPI(
            api_key=(
                api_key if api_key is not None else os.getenv("MISTRAL_API_KEY") or ""
            )
        )


class Mistral:
    def __init__(self, api_key: str | None = None):
        self.api = MistralAPI.create(api_key)
        self.models = ModelsWrapper(self.api)
        self.chat_completions = ChatCompletionsWrapper(self.api)
