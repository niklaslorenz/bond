import json
import logging
from pathlib import Path
from typing import overload

from bond.conversation.cache.temporary import TemporaryEpisodeCache
from bond.conversation.types import Episode

logger = logging.getLogger(__name__)


class FileMappedEpisodeCache(TemporaryEpisodeCache):
    @overload
    def __init__(
        self, base_path: None, name: None, episodes: list[Episode] | None = None
    ): ...

    @overload
    def __init__(
        self, base_path: Path, name: str, episodes: list[Episode] | None = None
    ): ...

    def __init__(
        self,
        base_path: Path | None,
        name: str | None,
        episodes: list[Episode] | None = None,
    ):
        super().__init__(episodes)
        self._dirty = False
        if (base_path is None) != (name is None):
            raise ValueError(
                "base_path and name must either both be set or both be None"
            )
        self._name = name
        self._base_path = base_path

    def mark_dirty(self, episode_index: int):
        self._dirty = True

    def move_to(self, name: str, base_path: Path):
        if self._name is not None and self._base_path is not None:
            old_file_path = self._base_path / (self._name + "_episodes.json")
        else:
            old_file_path = None
        self._name = name
        self._base_path = base_path
        self._dirty = True
        self.save()
        # Removing the old file after saving prevents data loss if saving crashes
        if old_file_path is not None and old_file_path.exists():
            old_file_path.unlink()

    def save_as(self, name: str, base_path: Path):
        file_path = base_path / (name + "_episodes.json")
        file_path.parent.mkdir(exist_ok=True, parents=True)
        episodes_data = [x.model_dump() for x in self._episodes]
        file_path.write_text(json.dumps(episodes_data, indent=2), encoding="utf-8")

    def save(self):
        if not self._dirty:
            return
        if self._base_path is None or self._name is None:
            raise RuntimeError("Cannot save temporary cache")
        self.save_as(self._name, self._base_path)

    @classmethod
    def load(cls, name: str, base_path: Path) -> "FileMappedEpisodeCache":
        file_path = base_path / (name + "_episodes.json")
        if not file_path.is_file():
            raise ValueError(f"Path {file_path} is not a file")
        episodes_data = json.loads(file_path.read_text(encoding="utf-8"))
        logger.debug(f"Number of loaded episodes: {len(episodes_data)}")
        episodes = [Episode.model_validate(x) for x in episodes_data]
        cache = FileMappedEpisodeCache(base_path, name, episodes)
        return cache

    @classmethod
    def exists(cls, name: str, base_path: Path) -> bool:
        return (base_path / (name + "_episodes.json")).is_file()
