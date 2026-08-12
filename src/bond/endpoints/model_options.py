from pydantic import BaseModel


def merge_options[OptType: BaseModel](
    t: type[OptType], options: list[OptType | None]
) -> OptType | None:
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
