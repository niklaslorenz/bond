from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel
from requests import Response

from bond.util import http_retry_loop


class ModelCapabilities(BaseModel):
    audio: bool = False
    audio_transcription: bool = False
    classification: bool = False
    completion_chat: bool = False
    completion_flm: bool = False
    fine_tuning: bool = False
    function_calling: bool = False
    moderation: bool = False
    ocr: bool = False
    vision: bool = False


class BaseModelCard(BaseModel):
    id: str
    aliases: list[str]
    capabilities: ModelCapabilities
    created: int
    default_model_temperature: float | None = None
    deprecation: datetime | None = None
    deprecation_replacement_model: str | None = None
    description: str | None = None
    max_context_length: int
    name: str | None = None
    object: Literal["model"]
    owned_by: str
    type: Literal["base"]


class ModelsProvider(Protocol):
    def retrieve_model(self, id: str) -> Response: ...
    def list_models(self) -> Response: ...


class ModelsWrapper:
    provider: ModelsProvider

    def __init__(self, provider: ModelsProvider):
        self.provider = provider

    def retrieve_model(self, id: str, max_retries: int = 3) -> BaseModelCard:
        response = http_retry_loop(
            lambda: self.provider.retrieve_model(id), max_retries
        )
        return BaseModelCard.model_validate(response.json())

    def list_models(self, max_retries: int = 3) -> list[BaseModelCard]:
        response = http_retry_loop(lambda: self.provider.list_models(), max_retries)
        response_json = response.json()
        assert response_json.get("object") == "list"
        return [BaseModelCard.model_validate(x) for x in response_json["data"]]
