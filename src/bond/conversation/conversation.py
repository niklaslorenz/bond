import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, PrivateAttr
from typing_extensions import deprecated

from bond.conversation.cache.base import EpisodeCache
from bond.conversation.cache.file_mapped import FileMappedEpisodeCache
from bond.conversation.task_list import TaskList
from bond.conversation.types import (
    ConversationMetadata,
    Episode,
    Turn,
)
from bond.conversation.working_set import WorkingSet

logger = logging.getLogger(__name__)

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
    working_set: WorkingSet | None = None
    task_list: TaskList | None = None
    metadata: ConversationMetadata = Field(default_factory=ConversationMetadata)

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
            self._episodes = FileMappedEpisodeCache(None, None)
            if len(self._episodes) == 0:
                self._episodes.append(Episode())
        return self._episodes

    @property
    def last_episode(self) -> Episode:
        if (last := self.episodes.last) is None:
            last = Episode()
            self.episodes.append(last)
        return last

    @property
    def storage_path(self) -> Path | None:
        """
        The directory where this conversation's episodes are stored.

        Returns ``None`` for volatile conversations.
        """
        return self._data_path

    @property
    def current_usage(self) -> int:
        last_turn = self.last_episode.last_turn
        if last_turn is None:
            return 0
        return last_turn.assistant_response.usage.total_tokens

    @storage_path.setter
    def storage_path(self, new_value: Path | None):
        self._data_path = new_value

    def add_turn(self, turn: Turn) -> None:
        self.last_episode.turns.append(turn)

    # TODO: use conversation.rollback instead
    @deprecated("use Conversation.rollback instead")
    def delete_turns(self, n: int) -> None:
        if n <= 0:
            raise ValueError("n must be strictly positive")
        ep = self.last_episode
        if ep is None:
            return
        if len(ep.turns) >= n:
            ep.turns = ep.turns[:-n]
            return
        ep_len = len(ep.turns)
        self.episodes.truncate(len(self.episodes) - 1)
        # NOTE: recursive call is ugly, but should work fine
        self.delete_turns(n - ep_len)

    def condense_turns(self, kept_turns: int):
        if kept_turns < 0:
            raise ValueError("kept_turns must be non-negative")
        split = max(0, len(self.last_episode.turns) - kept_turns)
        for turn in self.last_episode.turns[:split]:
            turn.condense()

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
        assert self.episodes
        last = self.episodes[-1]
        assert not last.is_finished
        if not last.turns:
            raise ValueError("Cannot archive an empty episode")
        if num_turns is None:
            num_turns = len(last.turns)
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

    def save(self, name: str | None, data_path: Path | None) -> None:
        """Save the conversation to a directory at *dir*.

        Writes ``metadata.json`` (name, persona, usage, etc.) and episode
        shards (``episodes_*.json``) into the same directory.

        If the conversation is already stored at *dir*, this only writes
        dirty shards and metadata — no copying is performed.
        """
        if data_path is None:
            data_path = self._data_path
        if name is None:
            name = self.name
        if data_path is None:
            raise ValueError("Could not determine data path")
        if name is None:
            raise ValueError("Could not determine name")
        data_path.mkdir(parents=True, exist_ok=True)

        # Write metadata (episodes are stored separately)
        metadata_path = data_path / f"{name}_metadata.json"
        metadata_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

        # Write episodes
        self.episodes.save_as(name, data_path)
        logger.debug(f"saved conversation to {data_path} as {name}")

    @classmethod
    def load(cls, name: str, data_path: Path) -> "Conversation":
        """
        Load a conversation from a directory at *path*.
        """
        logger.debug(f"Loading conversation {name}")
        metadata_path = data_path / f"{name}_metadata.json"
        conv = cls.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        conv.storage_path = data_path
        conv._episodes = FileMappedEpisodeCache.load(name, data_path)
        return conv

    @classmethod
    def exists(cls, name: str, data_path: Path) -> bool:
        if not (data_path / f"{name}_metadata.json").is_file():
            return False
        return FileMappedEpisodeCache.exists(name, data_path)
