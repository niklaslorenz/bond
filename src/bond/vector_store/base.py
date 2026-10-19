"""
Base interface for vector store implementations.

This module defines the abstract base class for all vector store implementations.
A vector store is responsible for storing embeddings and associated metadata,
and querying for the k-nearest neighbors of a given embedding.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

VectorStoreEmbedding = list[float]


class VectorStoreEntry(BaseModel):
    """
    Represents an entry stored in the vector store.

    Attributes:
        id: identifier
        content: The main content of the entry (e.g., text, data).
        timestamp: When the entry was stored (ISO format). Optional, defaults to None.
        outdated: Whether the entry is outdated and should be excluded from queries. Defaults to False.
    """

    id: int = 0
    content: str
    timestamp: str | None = None
    outdated: bool = False


class VectorStore(ABC):
    """
    Abstract base class for vector store implementations.

    All concrete vector store implementations (e.g., FAISS, Chroma, Weaviate)
    must implement the methods defined in this class.
    """

    @classmethod
    @abstractmethod
    def load_or_create(cls, path: Path) -> "VectorStore":
        """
        Load the vector store from the specified directory path.

        Args:
            path: The directory path where the vector store data is stored.
        """
        ...

    @abstractmethod
    def store(self, embedding: VectorStoreEmbedding, entry: VectorStoreEntry) -> None:
        """
        Store an entry in the vector store.

        Args:
            embedding: The embedding for the entry
            entry: The entry to store, containing content, metadata, and embedding.
        """
        ...

    @abstractmethod
    def mark_outdated(self, entry_id: int) -> VectorStoreEntry | None:
        """
        Mark an entry as outdated.

        Args:
            entry_id: The ID of the entry to mark as outdated.
        """
        ...

    @abstractmethod
    def query(self, embedding: VectorStoreEmbedding, k: int) -> list[VectorStoreEntry]:
        """
        Query the vector store for the k-nearest neighbors of the given embedding.

        Args:
            embedding: The embedding vector to query for.
            k: The number of nearest neighbors to return.

        Returns:
            A list of the k-nearest VectorStoreEntry objects, sorted by similarity.
        """
        ...

    @abstractmethod
    def write(self):
        pass
