import json
from typing import Any, ClassVar

from pydantic import BaseModel


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
    toolbox: list[str] = []
    model_options: dict[str, Any] = {}

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
