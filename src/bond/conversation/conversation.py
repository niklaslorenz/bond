import json
import shutil
import tempfile
from dataclasses import field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, PrivateAttr

from bond.conversation.episode_cache import EpisodeCache
from bond.conversation.types import (
    ConversationMessage,
    ConversationMetadata,
    Episode,
    SystemMessage,
    Turn,
    UserMessage,
)

EPISODES_PER_SHARD = 8


class Conversation(BaseModel):
    """A conversation stored as a list of episodes.

    The last episode is always *unfinished* (no ``episode_summary``). Its turns
    are the active turns, and its ``prefix_summary`` is the context summary
    for those turns.  Episodes are stored in an :class:`EpisodeCache` so that
    long conversations are sharded across files and only needed shards are
    loaded into memory.
    """

    name: str | None = None
    persona: str | None = None
    metadata: ConversationMetadata = field(default_factory=ConversationMetadata)

    _episodes: EpisodeCache | None = PrivateAttr(default=None)
    _data_path: Path | None = PrivateAttr(default=None)

    @property
    def episodes(self) -> EpisodeCache:
        """
        The episode cache backing this conversation.

        Lazily initialized on first access. If the conversation was loaded
        from disk, the cache reads shards from the conversation directory.
        Otherwise, a volatile cache is used.
        """
        if self._episodes is None:
            self._episodes = EpisodeCache(
                self._data_path, episodes_per_shard=EPISODES_PER_SHARD
            )
            if len(self._episodes) == 0:
                self._episodes.append(Episode())
        return self._episodes

    @property
    def storage_path(self) -> Path | None:
        """
        The directory where this conversation's episodes are stored.

        Returns ``None`` for volatile conversations.
        """
        return self._data_path

    def add_message(self, message: ConversationMessage) -> None:
        """
        Add a message to the current unfinished episode.

        User messages start a new turn. Assistant and tool messages are appended
        to the current turn.
        """
        message.timestamp = datetime.now(timezone.utc)

        if isinstance(message.message, SystemMessage):
            raise ValueError("System messages cannot be added to conversation history")

        if len(self.episodes) == 0:
            self.episodes.append(Episode())
        episode = self.episodes.last
        assert not episode.is_finished

        if isinstance(message.message, UserMessage):
            if episode.turns:
                last_turn = episode.turns[-1]
                if last_turn.messages and isinstance(
                    last_turn.messages[-1].message, UserMessage
                ):
                    raise ValueError(
                        "Cannot add user message: previous turn has no assistant response"
                    )
                # TODO: Add verification logic that ensures the correct order
                # of tool messages and assistant messages
            episode.turns.append(Turn(messages=[message]))
        else:
            if not episode.turns:
                raise ValueError(
                    "Cannot add assistant/tool message without a preceding user message"
                )
            episode.turns[-1].messages.append(message)

    # TODO: unreviewed
    def archive_turns(
        self,
        num_turns: int | None,
        episode_summary: str,
        prefix_summary: str,
    ) -> Episode:
        """Archive the oldest N turns from the current unfinished episode.

        Splits the last episode: the oldest N turns become a finished episode
        (keeping the original ``prefix_summary`` and ``episode_id``), and the
        remaining turns go into a new unfinished episode with the new
        ``prefix_summary``.

        ``episode_summary`` should summarize the turns being archived.
        ``prefix_summary`` should summarize all episodes before the new one.
        """
        if not self.episodes:
            # This should never happen because there should always be an unfinished episode
            raise RuntimeError("No episodes")
        last = self.episodes[-1]
        if not last.turns:
            raise ValueError("Cannot archive an empty episode")
        if num_turns is None:
            num_turns = len(last.turns)
        if last.is_finished:
            raise ValueError("Last episode is already finished")
        if num_turns <= 0:
            raise ValueError("num_turns must be positive")
        if num_turns > len(last.turns):
            raise ValueError(
                f"Cannot archive {num_turns} turns, " f"only {len(last.turns)} active"
            )

        archived_turns = last.turns[:num_turns]
        remaining_turns = last.turns[num_turns:]

        # The finished episode keeps the original ID and prefix
        finished = Episode(
            episode_id=last.episode_id,
            prefix_summary=last.prefix_summary,
            episode_summary=episode_summary,
            turns=archived_turns,
            summarized_at=datetime.now(timezone.utc),
        )
        self.episodes[-1] = finished

        # New unfinished episode gets the new prefix and remaining turns
        new_episode = Episode(
            prefix_summary=prefix_summary,
            turns=remaining_turns,
        )
        self.episodes.append(new_episode)

        return finished

    # TODO: unreviewed
    def rollback_to_turn(self, turn_id: str) -> None:
        """Roll back the conversation to the specified turn.

        Removes all turns after the specified turn and all episodes after the
        one containing it. If the turn was in a finished episode, that episode
        becomes unfinished (its ``episode_summary`` is cleared) and its turns
        become the active turns.
        """
        for ep_idx, episode in enumerate(self.episodes):
            for t_idx, turn in enumerate(episode.turns):
                if turn.turn_id == turn_id:
                    # Truncate turns to include only up to the target
                    episode.turns = episode.turns[: t_idx + 1]
                    # Mark episode as unfinished
                    episode.episode_summary = None
                    episode.summarized_at = None
                    # Mark the shard as dirty so modifications are persisted
                    self.episodes.mark_dirty(ep_idx)
                    # Remove all episodes after this one
                    if ep_idx < len(self.episodes) - 1:
                        self.episodes.truncate(ep_idx + 1)
                    return

        raise ValueError(f"Turn {turn_id} not found")

    def save(self) -> None:
        """Save the conversation to a directory at *dir*.

        Writes ``metadata.json`` (name, persona, usage, etc.) and episode
        shards (``episodes_*.json``) into the same directory.

        If the conversation is already stored at *dir*, this only writes
        dirty shards and metadata — no copying is performed.
        """
        if self._data_path is None:
            raise RuntimeError("Tried to save conversation with no data path")
        dir = self._data_path
        dir.mkdir(parents=True, exist_ok=True)

        # Write metadata (episodes are stored separately)
        metadata_path = dir / "metadata.json"
        metadata_path.write_text(self.model_dump_json(), encoding="utf-8")

        # Write episodes
        self.episodes.write()

    # TODO: unreviewed
    def move_to(
        self, dir: Path, *, on_existing: Literal["error", "replace"] = "error"
    ) -> None:
        """Move the conversation (metadata + episodes) to *dir*.

        Uses filesystem-level move (``shutil.move``) so that no data is
        duplicated.  After the move, the episode cache points to *dir* and
        shards are lazily reloaded from the new location.

        This is the preferred way to "rename" a conversation directory
        (e.g. from ``temp/`` to ``conversations/<name>/``) without copying
        episode data.

        Args:
            dir: Target directory for the conversation.
            on_existing: How to handle an existing conversation at *dir*
                (a ``metadata.json`` or ``episodes_*.json`` files already
                present).  ``"error"`` (the default) raises
                :class:`FileExistsError`; ``"replace"`` overwrites them.
        """
        dir.mkdir(parents=True, exist_ok=True)

        # Guard against silently overwriting an existing conversation's
        # metadata file (episode files are handled by EpisodeCache.move_to)
        metadata_path = dir / "metadata.json"
        if metadata_path.exists():
            if on_existing == "error":
                raise FileExistsError(
                    "Target directory already contains a conversation "
                    "(metadata.json exists)"
                )
            metadata_path.unlink()

        # Ensure the episode cache is initialised (creates temp dir if needed)
        _ = self.episodes

        # Write metadata to the new location
        metadata_path.write_text(self.model_dump_json(), encoding="utf-8")

        # Move episode shards (writes dirty shards first, then moves files)
        assert self._episodes is not None
        self._episodes.move_to(dir, on_existing=on_existing)

        self._data_path = dir

    @classmethod
    def create_at(cls, path: Path, *, clear: bool = False) -> "Conversation":
        """
        Create a fresh conversation with episodes stored at *path*.

        If *clear* is True, any existing data at *path* is deleted first.
        """
        if clear and path.exists():
            shutil.rmtree(path)
        conv = cls()
        conv._data_path = path
        return conv

    @classmethod
    def load(cls, dir: Path) -> "Conversation":
        """
        Load a conversation from a directory at *path*.
        """
        metadata_path = dir / "metadata.json"
        conv = cls.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        conv._data_path = dir
        return conv


# TODO: put this somewhere where it belongs
# ---------------------------------------------------------------------------
# Pointer helpers for last-conversation indirection
# ---------------------------------------------------------------------------


def write_pointer(pointer_file: Path, target_dir: Path, base_dir: Path) -> None:
    """Write a pointer file that references *target_dir* relative to *base_dir*.

    The pointer file is a small JSON document::

        {"path": "conversations/my-conv"}

    This allows the last-conversation location to be stored as a relative
    path, so the data directory can be moved without breaking the pointer.
    """
    rel = target_dir.relative_to(base_dir)
    pointer_file.parent.mkdir(parents=True, exist_ok=True)
    pointer_file.write_text(json.dumps({"path": str(rel)}, indent=2), encoding="utf-8")


def read_pointer(pointer_file: Path, base_dir: Path) -> Path | None:
    """Read a pointer file and return the absolute target path.

    Returns ``None`` if the pointer file does not exist or is malformed.
    """
    if not pointer_file.is_file():
        return None
    try:
        data = json.loads(pointer_file.read_text(encoding="utf-8"))
        return base_dir / data["path"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
