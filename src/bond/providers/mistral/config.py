from dataclasses import field
from typing import Literal

from pydantic import BaseModel

from bond.persona import SummarizationOptions


class MistralModelOptions(BaseModel):
    temperature: float = 0.7


class MistralConfig(BaseModel):
    type: Literal["mistral"] = "mistral"
    api_key: str
    models: list[str] | None = None
    chat_completion_options: MistralModelOptions | None = None
    summarization: SummarizationOptions[MistralModelOptions] | None = None
