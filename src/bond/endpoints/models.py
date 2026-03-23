from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel


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


class ModelsEndpoint(Protocol):
    def retrieve_model(self, id: str, max_retries: int = 3) -> BaseModelCard: ...
    def list_models(self, max_retries: int = 3) -> list[BaseModelCard]: ...
