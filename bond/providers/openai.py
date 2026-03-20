from typing import Literal

from pydantic import BaseModel


class OpenAIConfig(BaseModel):
    name: str
    type: Literal["openai"]
    api_key: str
    models: list[str]
