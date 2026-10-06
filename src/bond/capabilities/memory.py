from typing import Any, Protocol

from bond.vector_store.base import VectorStoreEntry


class MemoryCapability(Protocol):
    """Protocol defining the interface for memory capabilities."""

    def store(self, content: str) -> str:
        """
        Store a full natural language statement in memory.

        Args:
            content: The statement or fact to store (e.g., "The capital of France is Paris")

        Returns:
            The unique ID of the stored entry
        """
        ...

    def direct_query(self, query: str, k: int = 5) -> list[VectorStoreEntry]:
        """
        Perform a direct KNN lookup for semantically similar statements.

        Args:
            query: The search query in natural language
            k: Number of nearest neighbors to return

        Returns:
            List of matching VectorStoreEntry objects sorted by similarity
        """
        ...

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
        ...

    def release(self): ...
