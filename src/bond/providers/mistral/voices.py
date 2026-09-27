from typing import Literal

import requests
from pydantic import BaseModel

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


class MistralVoiceResponse(BaseModel):
    items: list[MistralVoiceResponseEntry]
    page: int
    page_size: int
    total: int
    total_pages: int


class MistralVoices:
    def __init__(self, config: MistralConfig):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {resolve_api_key(config.api_key)}",
        }

    def voices(self, max_retries: int = 3):
        response = http_retry_loop(
            lambda: requests.get(
                "https://api.mistral.ai/v1/audio/voices", headers=self.headers
            ),
            max_retries=max_retries,
        )
        data = MistralVoiceResponse.model_validate(response.json())
        return data
