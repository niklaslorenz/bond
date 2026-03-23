from abc import ABC
from typing import Any

from pydantic import BaseModel


class ModelOptions(ABC, BaseModel):
    def parse(self) -> dict[str, Any]:
        return self.model_dump()


def merge_options[OptType: ModelOptions](
    t: type[OptType], options: list[OptType | None]
) -> ModelOptions | None:
    merged = None
    for opt in options:
        if opt is None:
            continue
        if merged is None:
            merged = opt.model_dump()
        else:
            for k, v in opt.model_dump().items():
                merged[k] = v
    return t.model_validate(merged) if merged is not None else None
