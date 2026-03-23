from typing import Literal

from pydantic import BaseModel

from bond.endpoints.model_options import ModelOptions


class MistralChatCompletionOptions(ModelOptions):
    temperature: float = 0.7

    def merge(
        self, other: "MistralChatCompletionOptions | None"
    ) -> "MistralChatCompletionOptions":
        if other is None:
            return self
        merged = self.model_dump()
        for k, v in other.model_dump().items():
            merged[k] = v
        return MistralChatCompletionOptions.model_validate(merged)


class MistralConfig(BaseModel):
    type: Literal["mistral"] = "mistral"
    api_key: str
    models: list[str] | None = None
    chat_completion_options: MistralChatCompletionOptions | None = None
    model_specific_chat_completion_options: dict[str, MistralChatCompletionOptions] = {}
