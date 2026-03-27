from typing import Literal
from urllib.parse import urljoin

import requests
from pydantic import BaseModel

from bond.endpoints.models import BaseModelCard, ModelCapabilities
from bond.providers.ollama.config import OllamaConfig
from bond.util import http_retry_loop, resolve_api_key


class OllamaModelCard(BaseModel):
    object: Literal["model"] = "model"
    id: str
    created: int
    owned_by: str


class OllamaModels:
    def __init__(self, config: OllamaConfig):
        self.config = config
        self.headers = {"Content-Type": "application/json"}
        if config.api_key is not None:
            self.headers["Authorization"] = f"Bearer {resolve_api_key(config.api_key)}"

    def _build_model_card(self, ollama_card: OllamaModelCard) -> BaseModelCard:
        return BaseModelCard(
            id=ollama_card.id,
            aliases=[],
            capabilities=ModelCapabilities(
                audio=True,
                audio_transcription=True,
                classification=True,
                completion_chat=True,
                completion_flm=True,
                fine_tuning=True,
                function_calling=True,
                moderation=True,
                ocr=True,
                vision=True,
            ),
            created=ollama_card.created,
            max_context_length=self.config.max_context_length,
            object="model",
            owned_by=ollama_card.owned_by,
            type="base",
        )

    def retrieve_model(self, id: str, max_retries: int = 3) -> BaseModelCard:
        response = http_retry_loop(
            lambda: requests.get(urljoin(self.config.base_url, f"v1/models/{id}")),
            max_retries=max_retries,
        )
        ollama_card = OllamaModelCard.model_validate_json(response.json())
        return self._build_model_card(ollama_card)

    def list_models(self, max_retries: int = 3) -> list[BaseModelCard]:
        response = http_retry_loop(
            lambda: requests.get(urljoin(self.config.base_url, f"v1/models/")),
            max_retries=max_retries,
        )
        json = response.json()
        assert json["object"] == "list"
        return [
            self._build_model_card(OllamaModelCard.model_validate_json(card))
            for card in response.json()["data"]
        ]
