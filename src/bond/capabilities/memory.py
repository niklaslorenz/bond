from typing import Any, Protocol

from returns.result import Result


class MemoryCapability(Protocol):
    """Protocol defining the interface for memory capabilities."""

    def store(
        self, text: str, embedding: list[float], metadata: dict[str, Any] | None = None
    ) -> Result[None, str]:
        """Store a text with its embedding and optional metadata in memory."""
        ...

    def query(
        self, embedding: list[float], k: int = 1
    ) -> Result[list[tuple[str, dict[str, Any], float]], str]:
        """
        Query the memory for the k nearest neighbors.
        Returns a list of tuples containing (text, metadata, similarity_score).
        """
        ...
