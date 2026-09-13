import json
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class AutoSummarization(BaseModel):
    token_threshold: int | None = None
    """Number of input and output tokens that triggers an automatic summarization at the end ot the turn."""
    min_messages: int = 10
    """Minimum number of messages required to trigger an automatic summarization. Takes precedence over token_threshold"""
    max_messages: int = 30
    """Maximum number of messages before triggering an automatic summarization. Takes precedence over token_threshold"""


class SummarizationOptions(BaseModel):
    instruction: str
    """System prompt that is used for the summarization task"""
    model: str | None = None
    """The model to use for summarization. Falls back to the persona model if not specified."""
    keep: int = 10
    """The number of last messages to not summarize and keep as is"""
    model_options: dict[str, Any] | None = None
    """Model options for summarization"""
    auto_summarize: AutoSummarization | None = None
    """Options for automatic summarization"""


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
