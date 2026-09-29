import base64
from typing import Any

import requests
from pydantic import BaseModel

from bond.endpoints.tts import TTSResponse
from bond.providers.mistral.config import MistralConfig
from bond.util import http_retry_loop, resolve_api_key


class MistralTTSResponse(BaseModel):
    audio_data: str

    def decode(self) -> TTSResponse:
        return TTSResponse(wav_audio=base64.b64decode(self.audio_data, validate=True))


class MistralTTS:
    def __init__(self, config: MistralConfig):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {resolve_api_key(config.api_key)}",
            "Content-Type": "application/json",
        }

    def tts(
        self,
        model: str,
        voice: str,
        content: str,
        options: dict[str, Any],
        max_retries: int = 3,
    ) -> TTSResponse:
        payload = {
            "model": model,
            "input": content,
            "voice_id": voice,
            "response_format": "wav",
            **options,
        }
        response = http_retry_loop(
            lambda: requests.post(
                "https://api.mistral.ai/v1/audio/speech",
                headers=self.headers,
                json=payload,
                stream=False,
            ),
            max_retries=max_retries,
        )
        return MistralTTSResponse.model_validate(response.json()).decode()
