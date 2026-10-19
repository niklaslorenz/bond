"""Sharded episode storage for long conversations.

Episodes are split across multiple JSON files (shards) so that only the
shards that are actually needed have to be loaded into memory.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Iterator, overload

from returns.result import Result

from bond.conversation.types import Episode, Turn


class EpisodeCache(ABC):

    # Mutable Sequence Interface

    @overload
    def __getitem__(self, index: int) -> Episode: ...

    @overload
    def __getitem__(self, index: slice) -> list[Episode]: ...

    @abstractmethod
    def __getitem__(self, index: int | slice) -> Episode | list[Episode]: ...

    @overload
    def __setitem__(self, index: int, episodes: Episode) -> None: ...

    @overload
    def __setitem__(self, index: slice, episodes: Iterable[Episode]) -> None: ...

    @abstractmethod
    def __setitem__(
        self, index: int | slice, episodes: Episode | Iterable[Episode]
    ) -> None: ...

    @abstractmethod
    def __len__(self) -> int: ...

    def __iter__(self) -> Iterator[Episode]:
        for i in range(len(self)):
            yield self[i]

    # Cache Interface

    def iterate(
        self, start: int | None = None, stop: int | None = None
    ) -> Iterator[Episode]:
        if start is None:
            start = 0
        if stop is None:
            stop = len(self)
        if start < 0:
            start = max(0, len(self) + start)
        if stop < 0:
            stop = max(0, len(self) + stop)
        if stop <= start:
            return
        for i in range(start, stop):
            yield self[i]

    @property
    def last(self) -> Episode | None:
        """The last (most recent) episode in the cache."""
        if len(self) == 0:
            return None
        return self[len(self) - 1]

    def add_turn(self, turn: Turn) -> None:
        last = self.last
        if last is None:
            raise RuntimeError("No episode")
        last.turns.append(turn)
        self.mark_dirty(len(self) - 1)

    @abstractmethod
    def append(self, episode: Episode) -> None: ...

    @abstractmethod
    def truncate(self, length: int) -> None: ...

    @abstractmethod
    def mark_dirty(self, episode_index: int) -> None: ...

    @abstractmethod
    def save_as(self, name: str, base_path: Path) -> None: ...

    @abstractmethod
    def save(self) -> None: ...

    @abstractmethod
    def move_to(self, name: str, base_path: Path) -> None: ...
