from pathlib import Path
from typing import Iterable, overload

from returns.result import Failure

from bond.conversation.cache.base import EpisodeCache
from bond.conversation.types import Episode


class TemporaryEpisodeCache(EpisodeCache):
    def __init__(self, episodes: list[Episode] | None = None):
        self._episodes: list[Episode] = list(episodes) if episodes is not None else []

    def __len__(self) -> int:
        return len(self._episodes)

    @overload
    def __getitem__(self, index: int) -> Episode: ...

    @overload
    def __getitem__(self, index: slice) -> list[Episode]: ...

    def __getitem__(self, index: int | slice) -> Episode | list[Episode]:
        return self._episodes[index]

    @overload
    def __setitem__(self, index: int, episodes: Episode) -> None: ...

    @overload
    def __setitem__(self, index: slice, episodes: Iterable[Episode]) -> None: ...

    def __setitem__(
        self, index: int | slice, episodes: Episode | Iterable[Episode]
    ) -> None:
        if isinstance(index, int):
            if not isinstance(episodes, Episode):
                raise ValueError(
                    f"Value type mismatch. Expected Episode, got {type(episodes)}"
                )
            self._episodes[index] = episodes
        else:
            if not isinstance(episodes, list):
                raise ValueError(
                    f"Value type mismatch. Expected list, got {type(episodes)}"
                )
            self._episodes[index] = episodes

    def append(self, episode: Episode) -> None:
        self.mark_dirty(len(self))
        self._episodes.append(episode)

    def truncate(self, length: int) -> None:
        for i in range(length, len(self)):
            self.mark_dirty(i)
        self._episodes = self._episodes[:length]

    def mark_dirty(self, episode_index: int) -> None:
        pass

    def save_as(self, name: str, base_path: Path) -> Failure[str]:
        return Failure("Temporary cache cant save")
