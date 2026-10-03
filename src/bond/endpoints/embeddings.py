from typing import Any, Protocol

from pydantic import BaseModel


class EmbeddingResponse(BaseModel):
    """Response model for embedding requests."""

    embeddings: list[list[float]]
    usage: int


class EmbeddingsEndpoint(Protocol):
    """Protocol defining the interface for sentence embeddings endpoints."""

    def embeddings(
        self,
        model: str,
        input: str | list[str],
        options: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> EmbeddingResponse: ...
