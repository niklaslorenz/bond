from typing import Literal

import requests
from pydantic import BaseModel

from bond.endpoints.voices import VoicesResponse
from bond.providers.mistral.config import MistralConfig
from bond.util import http_retry_loop, resolve_api_key


class MistralVoiceResponseEntry(BaseModel):
    age: int | None
    color: str | None
    description: str | None
    gender: str | None
    id: str
    languages: list[str]
    name: str
    type: Literal["preset", "custom"]
    user_id: str | None


class MistralVoices:
    def __init__(self, config: MistralConfig):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {resolve_api_key(config.api_key)}",
        }

    def voices(
        self, limit: int = 10, offset: int = 0, max_retries: int = 3
    ) -> VoicesResponse:
        response = http_retry_loop(
            lambda: requests.get(
                "https://api.mistral.ai/v1/audio/voices",
                headers=self.headers,
                params={
                    "limit": limit,
                    "offset": offset,
                },
            ),
            max_retries=max_retries,
        )
        data = VoicesResponse.model_validate(response.json())
        return data
