import json
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class SummarizationOptions[ModelOptions: BaseModel](BaseModel):
    model: str | None = None
    """The model to use for summarization. Falls back to the persona model if not specified."""
    auto_summarize: bool = False
    """If set, summarization is """
    keep: int = 10
    """The number of last messages to not summarize and keep as is"""
    token_threshold: int | None = None
    """The total number of tokens in the last completion that will trigger a summarization"""
    min_unsummarized_messages: int = 10
    """The minumum number of unsummarized messages that need to exist before a summarization is triggered (takes precedence over token_threshold)"""
    max_unsummarized_messages: int = 30
    """The maximum number of unsummarized messages that can exist before a summarization is triggered (takes precedence over min_summarized_messages)"""
    system_prompt: str | None = None
    """System prompt that is used for the summarization task"""
    model_options: ModelOptions | None = None
    """Model options for summarization"""
    user_instruction: str | None = None
    """The user message that is appended to the message list in order to instruct the model to create the summary"""


class Persona(BaseModel):
    """
    Base Persona class that can be extended by plugins.

    Plugins can register subclasses with additional fields using
    `register_persona_type()` from the persona_registry module.

    Persona JSON files can specify a type discriminator to use a
    registered subclass:

    ```json
    {
      "type": "my_custom_persona",
      "name": "My Persona",
      "model": "my-model",
      "provider": "mistral",
      "custom_field": "custom_value"
    }
    ```

    If no "type" field is present, the base Persona class is used.
    """

    type: ClassVar[str] = "default"

    name: str
    model: str
    provider: str
    system_prompt: str | None = None
    toolbox: list[str] = Field(default_factory=list)
    model_options: dict[str, Any] = Field(default_factory=dict)
    summarization: SummarizationOptions | None = None

    @classmethod
    def get_type(cls) -> str:
        """Get the type discriminator for this persona class."""
        return getattr(cls, "type", "default")

    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON, including the type discriminator."""
        data = self.model_dump(**kwargs)
        persona_type = self.get_type()
        if persona_type != "default":
            data = {"type": persona_type, **data}
        return json.dumps(data, **kwargs)
