from typing import Protocol

from pydantic import BaseModel


class Voice(BaseModel):
    id: str
    name: str


class VoicesResponse(BaseModel):
    items: list[Voice]
    page: int
    page_size: int
    total: int
    total_pages: int


class VoicesEndpoint(Protocol):
    def voices(
        self, limit: int = 10, offset: int = 0, max_retries: int = 3
    ) -> VoicesResponse: ...


def list_all(endpoint: VoicesEndpoint, page_size: int = 10):
    page = endpoint.voices(page_size)
    for i in range(page.total_pages):
        if i != 0:
            page = endpoint.voices(page.page_size, offset=page.page_size * i)
        for voice in page.items:
            yield voice


def find_voice(
    endpoint: VoicesEndpoint, name: str, page_size: int = 10
) -> Voice | None:
    return next(
        filter(lambda voice: voice.name == name, list_all(endpoint, page_size)), None
    )
