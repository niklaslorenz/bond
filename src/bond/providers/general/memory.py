from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from bond.endpoints.embeddings import EmbeddingsEndpoint
from bond.vector_store.base import VectorStoreEntry

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class DefaultMemoryOptions(BaseModel):
    """Configuration options for the default memory capability."""

    model: str
    vector_store: str
    vector_store_type: str = "faiss"
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
        runtime: "BondRuntime | None",
        max_retries: int = 3,
    ):
        if runtime is None:
            from bond.runtime import BondRuntime

            runtime = BondRuntime.get_instance()
        self._options = options
        self._embeddings = embeddings
        self._runtime = runtime
        self._max_retries = max_retries
        self._vector_store = runtime.load_vector_store(
            options.vector_store, options.vector_store_type
        )

    def store(self, content: str) -> str:
        """
        Store a full natural language statement in memory.

        Args:
            content: The statement or fact to store

        Returns:
            The unique ID of the stored entry
        """
        # Get embedding for the content
        embedding_response = self._embeddings.embeddings(
            model=self._options.model,
            input=content,
            options=self._options.embedding_options,
            max_retries=self._max_retries,
        )
        embedding = embedding_response.embeddings[0]

        # Create and store the entry
        entry = VectorStoreEntry(content=content, timestamp=datetime.now().isoformat())
        self._vector_store.store(embedding, entry)

        # Return the ID (VectorStoreEntry uses auto-incrementing int ID)
        return str(entry.id)

    def direct_query(self, query: str, k: int = 5) -> list[VectorStoreEntry]:
        """
        Perform a direct KNN lookup for semantically similar statements.

        Args:
            query: The search query in natural language
            k: Number of nearest neighbors to return

        Returns:
            List of matching VectorStoreEntry objects sorted by similarity
        """
        # Get embedding for the query
        embedding_response = self._embeddings.embeddings(
            model=self._options.model,
            input=query,
            options=self._options.embedding_options,
            max_retries=self._max_retries,
        )
        embedding = embedding_response.embeddings[0]

        # Query the vector store
        results = self._vector_store.query(embedding, k)

        return results

    def deep_remember(self, query: str, max_iterations: int) -> list[VectorStoreEntry]:
        """
        Launch an agentic loop for deep memory search.

        Iteratively refines queries to explore the memory space and find
        relevant information that may not be captured by a single direct query.

        Args:
            query: The initial search query in natural language
            max_iterations: Maximum number of search iterations to perform

        Returns:
            List of relevant VectorStoreEntry objects found through iterative search
        """
        # TODO: Implement - agentic loop with iterative searching
        raise RuntimeError("Not implemented")

    def retire(self, entry_id: int) -> VectorStoreEntry | None:
        """
        Invalidate/retire a memory entry by marking it as outdated.

        Args:
            entry_id: The ID of the entry to retire
        """
        return self._vector_store.mark_outdated(entry_id)

    def release(self):
        self._vector_store.write()
