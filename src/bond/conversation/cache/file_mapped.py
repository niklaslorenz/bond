import json
from pathlib import Path
from typing import overload

from bond.conversation.cache.temporary import TemporaryEpisodeCache
from bond.conversation.types import Episode


class FileMappedEpisodeCache(TemporaryEpisodeCache):
    @overload
    def __init__(self, base_path: None, name: None): ...

    @overload
    def __init__(self, base_path: Path, name: str): ...

    def __init__(self, base_path: Path | None, name: str | None):
        super().__init__()
        self._dirty = False
        if (base_path is None) != (name is None):
            raise ValueError(
                "base_path and name must either both be set or both be None"
            )
        if base_path is not None and name is not None:
            self.load(name, base_path)

    def mark_dirty(self, episode_index: int):
        self._dirty = True

    def save_as(self, name: str, base_path: Path):
        if not self._dirty:
            return
        file_path = base_path / (name + "_episodes.json")
        file_path.parent.mkdir(exist_ok=True, parents=True)
        episodes_data = [x.model_dump() for x in self._episodes]
        file_path.write_text(json.dumps(episodes_data), encoding="utf-8")

    def load(self, name: str, base_path: Path):
        file_path = base_path / (name + "_episodes.json")
        if not file_path.exists():
            raise ValueError("Episode file does not exist.")
        if not file_path.is_file():
            raise ValueError(f"Path {file_path} is not a file")
        episodes_data = json.loads(file_path.read_text(encoding="utf-8"))
        episodes = [Episode.model_validate(x) for x in episodes_data]
        self._episodes = episodes
        self._dirty = False
