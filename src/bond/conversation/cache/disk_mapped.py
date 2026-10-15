import json
from pathlib import Path
from typing import Iterable, cast, overload

from bond.conversation.cache.base import EpisodeCache
from bond.conversation.types import Episode


class DiskMappedEpisodeCache(EpisodeCache):

    def __init__(self, path: Path | None, episodes_per_shard: int) -> None:
        if episodes_per_shard <= 0:
            raise ValueError("episodes_per_shard must be positive")
        self._path = path
        self._episodes_per_shard = episodes_per_shard
        self._shards: dict[int, list[Episode]] = {}
        self._dirty: set[int] = set()
        self._total: int | None = None

    @overload
    def __getitem__(self, index: int) -> Episode: ...

    @overload
    def __getitem__(self, index: slice) -> list[Episode]: ...

    def __getitem__(self, index: int | slice) -> Episode | list[Episode]:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return [self[i] for i in range(start, stop, step)]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("episode index out of range")
        shard_idx = index // self._episodes_per_shard
        offset = index % self._episodes_per_shard
        return self._load_shard(shard_idx)[offset]

    @overload
    def __setitem__(self, index: int, episodes: Episode) -> None: ...

    @overload
    def __setitem__(self, index: slice, episodes: Iterable[Episode]) -> None: ...

    def __setitem__(
        self, index: int | slice, episodes: Episode | Iterable[Episode]
    ) -> None:
        """Replace the episode(s) at *index*.

        With an integer index, *episode* must be a single :class:`Episode`.
        With a slice, *episode* must be an iterable of :class:`Episode` objects.
        Slice assignment can not change the total number of episodes.
        """
        if isinstance(index, slice):
            if isinstance(episodes, Episode):
                raise TypeError(
                    "slice assignment requires an iterable of Episode, "
                    "not a single Episode"
                )
            self._set_slice(index, episodes)
            return
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("episode index out of range")
        shard_idx = index // self._episodes_per_shard
        offset = index % self._episodes_per_shard
        shard = self._load_shard(shard_idx)
        shard[offset] = cast(Episode, episodes)
        self._dirty.add(shard_idx)

    def __len__(self) -> int:
        if self._total is None:
            self._total = self._compute_total()
        return self._total

    def append(self, episode: Episode) -> None:
        """Append *episode* to the cache, creating a new shard if necessary."""
        total = len(self)
        shard_idx = total // self._episodes_per_shard
        shard_offset = total % self._episodes_per_shard

        if shard_offset == 0:
            # New shard is needed
            self._shards[shard_idx] = []
        self._shards[shard_idx].append(episode)
        self._dirty.add(shard_idx)
        self._total = total + 1

    # TODO: Unreviewed
    def truncate(self, length: int) -> None:
        """Remove all episodes after index ``length - 1``.

        Truncates the shard containing the cutoff point and deletes all
        subsequent shards from memory and disk.
        """
        if length < 0:
            raise ValueError("length must be non-negative")
        total = len(self)
        if length >= total:
            return  # Nothing to do

        # Truncate the shard containing the cutoff point
        truncated_shard_idx = length // self._episodes_per_shard
        shard = self._load_shard(truncated_shard_idx)
        offset = length % self._episodes_per_shard
        del shard[offset:]
        self._dirty.add(truncated_shard_idx)

        # Remove all shards after the truncated shard
        last_shard_idx = (total - 1) // self._episodes_per_shard
        for shard_idx in range(truncated_shard_idx + 1, last_shard_idx + 1):
            self._shards.pop(shard_idx, None)
            shard_path = self._shard_path(shard_idx)
            if shard_path is not None and shard_path.exists():
                shard_path.unlink()

        self._total = length

    def mark_dirty(self, index: int) -> None:
        """Mark the shard containing the episode at *index* as dirty.

        Call this after mutating an episode obtained via ``__getitem__``
        (other than the last episode) to ensure the change is persisted.
        """
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("episode index out of range")
        shard_idx = index // self._episodes_per_shard
        self._dirty.add(shard_idx)

    def save_as(self, name: str, base_path: Path) -> None:
        if self._path is None:
            raise RuntimeError("Tried to write episode cache with no path set.")
        if not self._dirty:
            return
        self._path.mkdir(parents=True, exist_ok=True)
        for shard_idx in self._dirty:
            shard = self._shards[shard_idx]
            file_path = self._shard_path(shard_idx)
            assert file_path is not None
            data = [ep.model_dump(mode="json") for ep in shard]
            file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._dirty.clear()
        # Mark the last shard as dirty again so modifications to
        # ``self.last`` are persisted on the next write.
        if len(self) > 0:
            self._dirty.add((len(self) - 1) // self._episodes_per_shard)

    # TODO: unreviewed
    def move_to(
        self, dir: Path, *, on_existing: Literal["error", "replace"] = "error"
    ) -> None:
        """Move all shard files to *dir* and update the cache path.

        Writes any dirty shards first, then moves every ``episodes_*.json``
        file to *dir* using :func:`shutil.move` (which handles cross-device
        moves).  After the move, in-memory shards are cleared so they are
        lazily reloaded from the new location on next access.

        If *dir* is the same as the current path, this is a no-op.

        Args:
            dir: Target directory for the shard files.
            on_existing: How to handle ``episodes_*.json`` files already
                present in *dir*.  ``"error"`` (the default) raises
                :class:`FileExistsError`; ``"replace"`` deletes them first.
        """
        self.write()  # ensure all dirty shards are on disk
        dir.mkdir(parents=True, exist_ok=True)

        if self._path.resolve() == dir.resolve():
            return  # already at target

        # Guard against silently overwriting existing episode files
        existing = sorted(dir.glob("episodes_*.json"))
        if existing:
            if on_existing == "error":
                names = ", ".join(f.name for f in existing)
                raise FileExistsError(
                    f"Target directory already contains episode files: {names}"
                )
            for f in existing:
                f.unlink()

        # Move each shard file
        for shard_file in sorted(self._path.glob("episodes_*.json")):
            target = dir / shard_file.name
            shutil.move(str(shard_file), str(target))

        # Remove the old directory if it's now empty (ignore errors)
        try:
            self._path.rmdir()
        except OSError:
            pass

        # Reset in-memory state — shards will be lazily reloaded from new path
        self._path = dir
        self._shards.clear()
        self._dirty.clear()
        self._total = None

    @property
    def path(self) -> Path | None:
        """The directory where shard files are stored."""
        return self._path

    # -- internals ----------------------------------------------------------

    def _set_slice(self, index: slice, value: Iterable[Episode]) -> None:
        """Replace episodes in the slice *index* with *value*."""
        start, stop, step = index.indices(len(self))
        replacement = list(value)

        if step != 1:
            # Extended slice: replacement must have the same length
            indices = list(range(start, stop, step))
            if len(replacement) != len(indices):
                raise ValueError(
                    f"attempt to assign sequence of size {len(replacement)} "
                    f"to extended slice of size {len(indices)}"
                )
            for i, ep in zip(indices, replacement):
                self[i] = ep
            return

        # Regular slice: can change length
        if len(replacement) != stop - start:
            raise ValueError("Length changes with slices are not allowed")

        for i, ep in enumerate(replacement):
            self[start + i] = ep
        return

    def _load_shard(self, shard_idx: int) -> list[Episode]:
        """Return the shard at *shard_idx*, loading it from disk if necessary."""
        if shard_idx not in self._shards:
            read = self._read_shard(shard_idx)
            if read is None:
                raise ValueError("Shard does not exist")
            self._shards[shard_idx] = read
        return self._shards[shard_idx]

    def _read_shard(self, shard_idx: int) -> list[Episode] | None:
        """Read shard *shard_idx* from disk (empty list if it doesn't exist)."""
        file_path = self._shard_path(shard_idx)
        if file_path is None:
            return None
        if not file_path.exists():
            return []
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        return [Episode.model_validate(item) for item in raw]

    def _shard_path(self, shard_idx: int) -> Path | None:
        if self._path is None:
            return None
        return self._path / f"episodes_{shard_idx}.json"

    def _compute_total(self) -> int:
        """Compute the total number of episodes on disk by scanning shard files on disk."""
        assert self._total is None
        indices = self._list_shard_indices()
        if not indices:
            return 0
        max_idx = max(indices)
        last_shard = self._load_shard(max_idx)
        # Mark the last shard as dirty so modifications to ``self.last``
        # are persisted on the next write.
        self._dirty.add(max_idx)
        return max_idx * self._episodes_per_shard + len(last_shard)

    def _list_shard_indices(self) -> list[int] | None:
        """Return sorted shard indices found on disk."""
        if self._path is None:
            return None
        if not self._path.exists():
            return None
        indices: list[int] = []
        for file_path in self._path.glob("episodes_*.json"):
            parts = file_path.stem.split("_")
            if len(parts) == 2 and parts[0] == "episodes":
                indices.append(int(parts[1]))
        return sorted(indices)
