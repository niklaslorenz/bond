from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Persona(BaseModel):
    name: str
    model: str
    provider: str
    system_prompt: str | None = None
    toolbox: list[str] = []
    model_options: dict[str, Any] = {}

    @classmethod
    def load_from(cls, path: Path) -> "Persona":
        if not path.is_file():
            raise ValueError(f"Invalid path: {path}")
        if not path.suffix == ".json":
            raise ValueError(f"Invalid file extension, must be .json")
        return Persona.model_validate_json(path.read_text())
