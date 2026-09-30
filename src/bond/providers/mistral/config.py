from typing import Literal

from pydantic import BaseModel


class MistralConfig(BaseModel):
    type: Literal["mistral"] = "mistral"
    api_key: str
    models: list[str] | None = None
