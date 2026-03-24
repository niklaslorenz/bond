from typing import Literal

from pydantic import BaseModel

from bond.endpoints.model_options import ModelOptions


class OllamaChatCompletionOptions(ModelOptions):
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None
    stop: str | list[str] | None = None
    stream: bool | None = None
    temperature: float | None = None
    top_p: float | None = None
    reasoning_effort: Literal["high", "medium", "low", "none"]


class OllamaConfig(BaseModel):
    type: Literal["ollama"]
    base_url: str
    api_key: str | None = None
    models: list[str] | None = None
    chat_completion_options: OllamaChatCompletionOptions | None = None
    model_specific_chat_completion_options: (
        dict[str, OllamaChatCompletionOptions] | None
    ) = None
