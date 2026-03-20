from abc import ABC
from typing import Any

from pydantic import BaseModel


class ModelOptions(ABC, BaseModel):
    def parse(self) -> dict[str, Any]:
        return self.model_dump()
