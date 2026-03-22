from typing import Literal

from pydantic import BaseModel

from bond.endpoints.model_options import ModelOptions


class MistralChatCompletionOptions(ModelOptions):
    temperature: float = 0.7


class MistralConfig(BaseModel):
    type: Literal["mistral"] = "mistral"
    api_key: str
    models: list[str] | None = None
    chat_completion_options: MistralChatCompletionOptions | None = None
    model_specific_chat_completion_options: (
        dict[str, MistralChatCompletionOptions] | None
    ) = None
