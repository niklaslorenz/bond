from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from bond.endpoints.embeddings import EmbeddingsEndpoint

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class DefaultMemoryOptions(BaseModel):
    """Configuration options for the default memory capability."""

    model: str
    vector_store: str
    embedding_options: dict[str, Any] | None = None


class DefaultMemoryCapability:
    """
    Default implementation of MemoryCapability using in-memory storage.
    Uses cosine similarity for vector comparisons.
    """

    def __init__(
        self,
        options: DefaultMemoryOptions,
        embeddings: EmbeddingsEndpoint,
        runtime: "BondRuntime",
        max_retries: int = 3,
    ):
        self._options = options
        self._embeddings = embeddings
        self._runtime = runtime
        self._max_retries = max_retries
        self._vector_store = runtime.load_vector_store(options.vector_store)
