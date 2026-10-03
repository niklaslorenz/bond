from typing import Any

import requests
from pydantic import BaseModel

from bond.endpoints.embeddings import EmbeddingResponse
from bond.providers.mistral.config import MistralConfig
from bond.util import http_retry_loop, resolve_api_key


class MistralEmbeddingUsageInfo(BaseModel):
    total_tokens: int


class MistralEmbeddingResponseData(BaseModel):
    embedding: list[float]
    index: int


class MistralEmbeddingsResponse(BaseModel):
    data: list[MistralEmbeddingResponseData]
    id: str
    model: str
    usage: MistralEmbeddingUsageInfo


class MistralEmbeddings:
    def __init__(self, config: MistralConfig):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {resolve_api_key(config.api_key)}",
            "Content-Type": "application/json",
        }

    def embeddings(
        self,
        model: str,
        input: str | list[str],
        options: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> EmbeddingResponse:
        if self.config.models is not None and model not in self.config.models:
            raise ValueError(f"This model is not whitelisted: {model}")

        # Ensure input is a list
        input_list = [input] if isinstance(input, str) else input

        payload = {
            "model": model,
            "input": input_list,
            "encoding_format": "float",
            "output_dtype": "float",
            **(options or {}),
        }

        response = http_retry_loop(
            lambda: requests.post(
                "https://api.mistral.ai/v1/embeddings",
                headers=self.headers,
                json=payload,
            ),
            max_retries=max_retries,
        )

        mistral_response = MistralEmbeddingsResponse.model_validate(response.json())
        embeddings = [
            entry.embedding
            for entry in sorted(mistral_response.data, key=lambda x: x.index)
        ]
        return EmbeddingResponse(
            embeddings=embeddings, usage=mistral_response.usage.total_tokens
        )
