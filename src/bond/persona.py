import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field

from bond.util import resolve_instruction

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


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

    @classmethod
    def from_file(cls, file: Path, runtime: "BondRuntime | None"):
        if runtime is None:
            from bond.runtime import BondRuntime
            runtime = BondRuntime.get_instance()
        if not file.exists():
            raise ValueError(f"Could not load persona from file: '{file}'. Does not exist.")
        data = json.loads(file.read_text(encoding="utf-8"))
        if (persona_type_name := data.get("type")) is not None:
            if (
                persona_type := runtime._persona_type_registry.get(persona_type_name)
            ) is None:
                raise ValueError(
                    f"Unknown persona type in {file}: {persona_type_name}. Valid values are {runtime._persona_type_registry.get_names()}"
                )
        else:
            persona_type = Persona
        persona = persona_type.model_validate(data)
        if (summarization := persona.summarization) is not None:
            summarization.instruction = resolve_instruction(summarization.instruction, runtime)
        return persona
        

    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON, including the type discriminator."""
        data = self.model_dump(**kwargs)
        persona_type = self.get_type()
        if persona_type != "default":
            data = {"type": persona_type, **data}
        return json.dumps(data, **kwargs)
