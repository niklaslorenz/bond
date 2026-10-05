"""
FAISS-based vector store implementation.

This module provides a concrete implementation of the VectorStore interface
using the FAISS library for efficient similarity search.
"""

import bisect
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np
from pydantic import BaseModel

from bond.vector_store.base import VectorStore, VectorStoreEmbedding, VectorStoreEntry


@dataclass
class FAISSShard:
    path: Path
    entries: list[VectorStoreEntry] = field(default_factory=list)
    dirty: bool = False

    def insert(self, entry: VectorStoreEntry):
        bisect.insort(self.entries, entry, key=lambda x: x.id)
        self.dirty = True

    def find(self, id: int) -> VectorStoreEntry | None:
        index = bisect.bisect_left(self.entries, id, key=lambda x: x.id)
        if index < len(self.entries) and index >= 0:
            entry = self.entries[index]
            if entry.id == id:
                return entry
        return None

    def write(self):
        data = [entry.model_dump() for entry in self.entries]
        self.path.write_text(json.dumps(data), encoding="utf-8")
        self.dirty = False

    @classmethod
    def load(cls, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = [VectorStoreEntry.model_validate(d) for d in data]
        return FAISSShard(path, entries)

    @classmethod
    def load_or_create(cls, path: Path):
        if path.exists():
            return cls.load(path)
        return FAISSShard(path)


class FAISSShardCache:
    """
    An LRU cache for FAISS shards that manages dirty flags and persists
    shards to disk when they are evicted and marked as dirty.

    Attributes:
        _cache: OrderedDict mapping shard names to (shard_data, is_dirty) tuples.
        _max_size: Maximum number of shards to keep in memory.
        _path: Base path where shards are stored.
    """

    def __init__(self, max_size: int, base_path: Path):
        """
        Initialize the shard cache.

        Args:
            max_size: Maximum number of shards to keep in memory.
            base_path: Base directory where shards are stored.
        """
        self._cache: OrderedDict[str, FAISSShard] = OrderedDict()
        self._max_size = max_size
        self._path = base_path

    def get(self, shard_name: str) -> FAISSShard | None:
        """
        Get a shard from the cache, moving it to the end (most recently used).

        Args:
            shard_name: Name of the shard to retrieve. Defaults to SHARD_NAME.

        Returns:
            The list of VectorStoreEntry objects for this shard.
        """
        if shard_name in self._cache:
            # Move to end to mark as recently used
            self._cache.move_to_end(shard_name)
            return self._cache[shard_name]
        return None

    def put(self, shard: FAISSShard, shard_name: str) -> None:
        """
        Put a shard into the cache, evicting the least recently used if necessary.

        Args:
            entries: The list of VectorStoreEntry objects to store.
            shard_name: Name of the shard. Defaults to SHARD_NAME.
            dirty: Whether the shard has been modified and needs to be persisted.
        """
        # If shard already exists, update it
        if shard_name in self._cache:
            self._cache.move_to_end(shard_name)
            self._cache[shard_name] = shard
            return

        # Evict oldest if at capacity
        if len(self._cache) >= self._max_size:
            _, old_shard = self._cache.popitem(last=False)
            if old_shard.dirty:
                old_shard.write()

        # Add new shard
        self._cache[shard_name] = shard

    def mark_dirty(self, shard_name: str) -> None:
        """
        Mark a shard as dirty (needs to be persisted).

        Args:
            shard_name: Name of the shard to mark. Defaults to SHARD_NAME.
        """
        shard = self._cache.get(shard_name)
        if shard is None:
            raise RuntimeError("shard is not in cache")
        shard.dirty = True

    def flush(self) -> None:
        """
        Write all dirty shards to disk.
        """
        for _, shard in list(self._cache.items()):
            if shard.dirty:
                shard.write()

    def __contains__(self, shard_name: str) -> bool:
        return shard_name in self._cache


class FAISSVectorStoreConfig(BaseModel):
    files_per_shard: int


class FAISSVectorStore(VectorStore):
    """
    A vector store implementation using FAISS (Facebook AI Similarity Search).

    FAISS is a library for efficient similarity search and clustering of dense vectors.
    This implementation stores embeddings in a FAISS index and maintains a separate
    metadata store for the associated content and metadata.
    """

    def __init__(
        self,
        config: FAISSVectorStoreConfig,
        index: faiss.Index | None,
        path: Path,
        shard_cache: FAISSShardCache,
    ):
        """Initialize the FAISS vector store."""
        self._config = config
        self._index = index
        self._path = path
        self._shard_cache = shard_cache

    @classmethod
    def load_or_create(
        cls, path: Path, shard_cache_size: int = 10, files_per_shard: int = 512
    ) -> "FAISSVectorStore":
        """
        Load the vector store from the specified directory path.

        Args:
            path: The directory path where the FAISS index and metadata are stored.
            shard_cache_size: Maximum number of shards to keep in the cache. Defaults to 10.
        """
        path.mkdir(parents=True, exist_ok=True)

        # Load config
        config_path = path / "vector-store.json"
        if config_path.exists():
            config = FAISSVectorStoreConfig.model_validate_json(
                config_path.read_text(encoding="utf-8")
            )
        else:
            config = FAISSVectorStoreConfig(files_per_shard=files_per_shard)

        # Load FAISS index
        index_file = path / "index.faiss"
        if index_file.exists():
            index = faiss.read_index(str(index_file))
        else:
            index = None

        shard_cache = FAISSShardCache(shard_cache_size, path)
        return FAISSVectorStore(config, index, path, shard_cache)

    def store(self, embedding: VectorStoreEmbedding, entry: VectorStoreEntry) -> None:
        """
        Store an entry in the vector store.

        Args:
            embedding: The embedding to store.
            entry: The entry to store, containing content, metadata, and embedding.

        Raises:
            ValueError: If the embedding is None or empty.
        """

        # Initialize index on first store if needed
        if self._index is None:
            embedding_dim = len(embedding)
            self._index = faiss.IndexFlatL2(embedding_dim)

        # Add embedding to FAISS index
        embedding_array = np.array([embedding], dtype=np.float32)
        idx = self._index.ntotal
        self._index.add(embedding_array)

        entry.id = idx
        shard_id = self._shard_id(idx)
        shard_name = self._shard_name(shard_id)
        shard = self._get_shard(shard_name)
        shard.insert(entry)

    def query(self, embedding: list[float], k: int = 1) -> list[VectorStoreEntry]:
        """
        Query the vector store for the k-nearest neighbors of the given embedding.

        Args:
            embedding: The embedding vector to query for.
            k: The number of nearest neighbors to return.

        Returns:
            A list of the k-nearest VectorStoreEntry objects, sorted by similarity.

        Raises:
            RuntimeError: If the index is not loaded.
        """
        if self._index is None:
            return []

        # Query FAISS index
        embedding_array = np.array([embedding], dtype=np.float32)
        _, indices = self._index.search(embedding_array, k)

        results = list(
            filter(
                None,
                (
                    self._get_shard(self._shard_name(idx)).find(idx)
                    for idx in indices[0]
                ),
            )
        )
        return results

    def _shard_name(self, shard_number: int) -> str:
        return f"data_{shard_number}"

    def _shard_id(self, id) -> int:
        return id // self._config.files_per_shard

    def _load_shard(self, shard_name: str) -> FAISSShard:
        shard = FAISSShard.load_or_create(self._path / (shard_name + ".json"))
        self._shard_cache.put(shard, shard_name)
        return shard

    def _get_shard(self, shard_name: str) -> FAISSShard:
        return self._shard_cache.get(shard_name) or self._load_shard(shard_name)
