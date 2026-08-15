import json
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from bond.runtime import BondRuntime

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
    def load_from(cls, path: Path | str) -> "Persona":
        """
        Load a Persona from a JSON file.

        Uses the registered persona type registry to support custom
        persona subclasses defined by plugins.

        Args:
            path: Path to the persona JSON file (as Path or string)

        Returns:
            A Persona instance (or subclass instance if type discriminator is set)

        Raises:
            ValueError: If the path is invalid or JSON is malformed
        """
        path = Path(path) if isinstance(path, str) else path

        if not path.is_file():
            raise ValueError(f"Invalid path: {path}")
        if not path.suffix == ".json":
            raise ValueError(f"Invalid file extension, must be .json")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if "type" in data:
            registry = BondRuntime.get_instance().persona_registry
            persona_type = registry.get(data["type"])
            if persona_type is None:
                raise ValueError(f"Unknown persona type: {data['type']}")
        else:
            persona_type=Persona
        return persona_type.model_validate(data)

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
