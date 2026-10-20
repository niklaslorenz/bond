"""Tests for bond.conversation.conversation module."""

import json

import pytest

from bond.conversation.cache.file_mapped import FileMappedEpisodeCache
from bond.conversation.conversation import Conversation
from bond.conversation.task_list import TaskList
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    ConversationMetadata,
    Episode,
    TextChunk,
    ToolCall,
    FunctionCall,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
)
from bond.conversation.working_set import WorkingSet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_usage(total_tokens: int = 30) -> UsageInfo:
    return UsageInfo(completion_tokens=10, prompt_tokens=20, total_tokens=total_tokens)


def make_turn(
    user_text: str = "Hello",
    assistant_text: str = "Hi",
    total_tokens: int = 30,
) -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create(user_text),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(content=[TextChunk(text=assistant_text)]),
            name="assistant",
            usage=make_usage(total_tokens),
        ),
    )


def make_turn_with_tool_calls() -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create("Search for something"),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(
                content=[TextChunk(text="Let me search...")],
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        function=FunctionCall(name="search", arguments={"q": "test"}),
                    )
                ],
            ),
            name="assistant",
            usage=make_usage(),
        ),
    )


# ---------------------------------------------------------------------------
# Creation & Defaults
# ---------------------------------------------------------------------------


class TestConversationCreation:
    def test_default_creation(self):
        conv = Conversation()
        assert conv.name is None
        assert conv.persona is None
        assert conv.working_set is None
        assert conv.task_list is None
        assert isinstance(conv.metadata, ConversationMetadata)

    def test_creation_with_name(self):
        conv = Conversation(name="my_conversation")
        assert conv.name == "my_conversation"

    def test_creation_with_persona(self):
        conv = Conversation(persona="helpful_assistant")
        assert conv.persona == "helpful_assistant"

    def test_creation_with_working_set(self):
        ws = WorkingSet()
        conv = Conversation(working_set=ws)
        assert conv.working_set is ws

    def test_creation_with_task_list(self):
        tl = TaskList()
        conv = Conversation(task_list=tl)
        assert conv.task_list is tl

    def test_creation_with_metadata(self):
        meta = ConversationMetadata(mistral_cache_key="abc123")
        conv = Conversation(metadata=meta)
        assert conv.metadata.mistral_cache_key == "abc123"

    def test_storage_path_none_by_default(self):
        conv = Conversation()
        assert conv.storage_path is None


# ---------------------------------------------------------------------------
# episodes property (lazy initialization)
# ---------------------------------------------------------------------------


class TestConversationEpisodes:
    def test_episodes_lazy_init_creates_cache(self):
        conv = Conversation()
        assert conv._episodes is None
        episodes = conv.episodes
        assert episodes is not None
        assert conv._episodes is not None

    def test_episodes_creates_initial_episode(self):
        """If cache is empty, a new Episode should be appended."""
        conv = Conversation()
        episodes = conv.episodes
        assert len(episodes) == 1

    def test_episodes_returns_same_cache_on_subsequent_access(self):
        conv = Conversation()
        episodes1 = conv.episodes
        episodes2 = conv.episodes
        assert episodes1 is episodes2

    def test_episodes_is_file_mapped_cache(self):
        conv = Conversation()
        assert isinstance(conv.episodes, FileMappedEpisodeCache)


# ---------------------------------------------------------------------------
# last_episode property
# ---------------------------------------------------------------------------


class TestConversationLastEpisode:
    def test_last_episode_returns_episode(self):
        conv = Conversation()
        last = conv.last_episode
        assert isinstance(last, Episode)

    def test_last_episode_creates_if_none(self):
        """If no episodes exist, last_episode should create one."""
        conv = Conversation()
        # Don't access episodes first
        assert conv._episodes is None
        last = conv.last_episode
        assert isinstance(last, Episode)
        assert len(conv.episodes) == 1

    def test_last_episode_returns_actual_last(self):
        conv = Conversation()
        conv.episodes.append(Episode())
        conv.episodes.append(Episode())
        last = conv.last_episode
        assert last is conv.episodes[-1]


# ---------------------------------------------------------------------------
# storage_path property & setter
# ---------------------------------------------------------------------------


class TestConversationStoragePath:
    def test_storage_path_default_none(self):
        conv = Conversation()
        assert conv.storage_path is None

    def test_storage_path_setter(self, tmp_path):
        conv = Conversation()
        conv.storage_path = tmp_path
        assert conv.storage_path == tmp_path
        assert conv._data_path == tmp_path

    def test_storage_path_setter_none(self, tmp_path):
        conv = Conversation()
        conv.storage_path = tmp_path
        conv.storage_path = None
        assert conv.storage_path is None


# ---------------------------------------------------------------------------
# current_usage property
# ---------------------------------------------------------------------------


class TestConversationCurrentUsage:
    def test_current_usage_zero_when_no_turns(self):
        conv = Conversation()
        assert conv.current_usage == 0

    def test_current_usage_returns_last_turn_tokens(self):
        conv = Conversation()
        conv.add_turn(make_turn(total_tokens=100))
        assert conv.current_usage == 100

    def test_current_usage_updates_with_new_turn(self):
        conv = Conversation()
        conv.add_turn(make_turn(total_tokens=50))
        conv.add_turn(make_turn(total_tokens=150))
        assert conv.current_usage == 150


# ---------------------------------------------------------------------------
# add_turn
# ---------------------------------------------------------------------------


class TestConversationAddTurn:
    def test_add_turn_adds_to_last_episode(self):
        conv = Conversation()
        turn = make_turn("Hello")
        conv.add_turn(turn)
        assert len(conv.last_episode.turns) == 1
        assert conv.last_episode.turns[0] is turn

    def test_add_multiple_turns(self):
        conv = Conversation()
        conv.add_turn(make_turn("First"))
        conv.add_turn(make_turn("Second"))
        conv.add_turn(make_turn("Third"))
        assert len(conv.last_episode.turns) == 3


# ---------------------------------------------------------------------------
# delete_turns
# ---------------------------------------------------------------------------


class TestConversationDeleteTurns:
    def test_delete_turns_raises_for_zero(self):
        conv = Conversation()
        with pytest.raises(ValueError, match="strictly positive"):
            conv.delete_turns(0)

    def test_delete_turns_raises_for_negative(self):
        conv = Conversation()
        with pytest.raises(ValueError, match="strictly positive"):
            conv.delete_turns(-1)

    def test_delete_turns_removes_from_last_episode(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))
        conv.add_turn(make_turn("3"))
        conv.delete_turns(1)
        assert len(conv.last_episode.turns) == 2

    def test_delete_turns_multiple(self):
        conv = Conversation()
        for i in range(5):
            conv.add_turn(make_turn(f"Turn {i}"))
        conv.delete_turns(2)
        assert len(conv.last_episode.turns) == 3

    def test_delete_turns_all_keeps_empty_episode(self):
        """Deleting all turns should keep one empty episode."""
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))
        conv.delete_turns(2)
        assert len(conv.last_episode.turns) == 0
        # Should still have one episode
        assert len(conv.episodes) == 1

    def test_delete_turns_more_than_exist(self):
        """Deleting more turns than exist should not cause infinite recursion.

        This was a bug in the old recursive implementation.
        """
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))
        # Delete 10 turns when only 2 exist
        conv.delete_turns(10)
        # All turns should be gone, but one empty episode remains
        assert len(conv.episodes) == 1
        assert len(conv.episodes[0].turns) == 0

    def test_delete_turns_exact_count(self):
        """Deleting exactly the number of turns that exist."""
        conv = Conversation()
        for i in range(3):
            conv.add_turn(make_turn(f"Turn {i}"))
        conv.delete_turns(3)
        assert len(conv.episodes) == 1
        assert len(conv.episodes[0].turns) == 0

    def test_delete_turns_on_empty_conversation(self):
        """Deleting from an empty conversation should not crash."""
        conv = Conversation()
        # No turns added - should have one empty episode
        conv.delete_turns(5)
        assert len(conv.episodes) == 1
        assert len(conv.episodes[0].turns) == 0

    def test_delete_turns_across_episodes(self):
        """Deleting turns should span across multiple episodes."""
        conv = Conversation()
        # Add 3 turns to first episode
        for i in range(3):
            conv.add_turn(make_turn(f"Turn {i}"))
        # Archive to create a second episode
        conv.archive_turns(None, "Summary", "Prefix")
        # Add 2 turns to second episode
        conv.add_turn(make_turn("Turn 3"))
        conv.add_turn(make_turn("Turn 4"))

        assert len(conv.episodes) == 2

        # Delete 3 turns: should remove 2 from second episode + 1 from first
        conv.delete_turns(3)

        # Should now have 2 episodes (first one has 2 turns left)
        total_turns = sum(len(ep.turns) for ep in conv.episodes)
        assert total_turns == 2

    def test_delete_turns_removes_entire_episodes(self):
        """If deletion spans entire episodes, those episodes should be removed."""
        conv = Conversation()
        # Episode 1: 2 turns
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))
        conv.archive_turns(None, "Summary 1", "Prefix")
        # Episode 2: 2 turns
        conv.add_turn(make_turn("3"))
        conv.add_turn(make_turn("4"))
        conv.archive_turns(None, "Summary 2", "Prefix")
        # Episode 3: 1 turn
        conv.add_turn(make_turn("5"))

        assert len(conv.episodes) == 3

        # Delete 4 turns: removes all of episode 3 (1) + episode 2 (2) + 1 from episode 1
        conv.delete_turns(4)

        # Should have 1 episode left with 1 turn
        assert len(conv.episodes) == 1
        assert len(conv.episodes[0].turns) == 1

    def test_delete_turns_preserves_remaining_turns(self):
        """Turns before the deletion point should be preserved."""
        conv = Conversation()
        turns = [make_turn(f"Turn {i}") for i in range(5)]
        for t in turns:
            conv.add_turn(t)

        conv.delete_turns(2)

        remaining = conv.last_episode.turns
        assert len(remaining) == 3
        assert remaining[0].turn_id == turns[0].turn_id
        assert remaining[1].turn_id == turns[1].turn_id
        assert remaining[2].turn_id == turns[2].turn_id


# ---------------------------------------------------------------------------
# condense_turns
# ---------------------------------------------------------------------------


class TestConversationCondenseTurns:
    def test_condense_turns_raises_for_negative(self):
        conv = Conversation()
        with pytest.raises(ValueError, match="non-negative"):
            conv.condense_turns(-1)

    def test_condense_turns_zero_keeps_none(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))
        conv.condense_turns(0)
        # All turns should be condensed
        assert all(t.condensed for t in conv.last_episode.turns)

    def test_condense_turns_keeps_last_n(self):
        conv = Conversation()
        for i in range(5):
            conv.add_turn(make_turn(f"Turn {i}"))
        conv.condense_turns(2)
        turns = conv.last_episode.turns
        # First 3 should be condensed, last 2 should not
        assert turns[0].condensed is True
        assert turns[1].condensed is True
        assert turns[2].condensed is True
        assert turns[3].condensed is False
        assert turns[4].condensed is False

    def test_condense_turns_more_than_available(self):
        """If kept_turns >= len(turns), nothing should be condensed."""
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))
        conv.condense_turns(5)
        assert all(not t.condensed for t in conv.last_episode.turns)


# ---------------------------------------------------------------------------
# archive_turns
# ---------------------------------------------------------------------------


class TestConversationArchiveTurns:
    def test_archive_raises_for_empty_episode(self):
        conv = Conversation()
        # last_episode is empty by default
        with pytest.raises(ValueError, match="empty episode"):
            conv.archive_turns(1, "summary", "prefix")

    def test_archive_raises_for_zero_turns(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        with pytest.raises(ValueError, match="must be positive"):
            conv.archive_turns(0, "summary", "prefix")

    def test_archive_raises_for_too_many_turns(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        with pytest.raises(ValueError, match="Cannot archive"):
            conv.archive_turns(5, "summary", "prefix")

    def test_archive_creates_finished_episode(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))

        finished = conv.archive_turns(1, "Episode summary", "New prefix")

        assert finished.is_finished is True
        assert finished.episode_summary == "Episode summary"
        assert len(finished.turns) == 1

    def test_archive_creates_new_unfinished_episode(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))

        conv.archive_turns(1, "Summary", "New prefix")

        assert len(conv.episodes) == 2
        new_episode = conv.episodes[-1]
        assert new_episode.is_finished is False
        assert new_episode.prefix_summary == "New prefix"
        assert len(new_episode.turns) == 1

    def test_archive_none_archives_all(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        conv.add_turn(make_turn("2"))

        finished = conv.archive_turns(None, "All", "Prefix")

        assert len(finished.turns) == 2
        assert len(conv.episodes[-1].turns) == 0

    def test_archive_preserves_episode_id(self):
        conv = Conversation()
        original_id = conv.last_episode.episode_id
        conv.add_turn(make_turn("1"))

        finished = conv.archive_turns(1, "Summary", "Prefix")

        assert finished.episode_id == original_id


# ---------------------------------------------------------------------------
# rollback_to_turn
# ---------------------------------------------------------------------------


class TestConversationRollbackToTurn:
    def test_rollback_raises_for_unknown_turn(self):
        conv = Conversation()
        conv.add_turn(make_turn("1"))
        with pytest.raises(ValueError, match="not found"):
            conv.rollback_to_turn("nonexistent_id")

    def test_rollback_removes_turns_after_target(self):
        conv = Conversation()
        turn1 = make_turn("1")
        turn2 = make_turn("2")
        turn3 = make_turn("3")
        conv.add_turn(turn1)
        conv.add_turn(turn2)
        conv.add_turn(turn3)

        conv.rollback_to_turn(turn1.turn_id)

        assert len(conv.last_episode.turns) == 1
        assert conv.last_episode.turns[0].turn_id == turn1.turn_id

    def test_rollback_to_last_turn_is_noop(self):
        conv = Conversation()
        turn1 = make_turn("1")
        turn2 = make_turn("2")
        conv.add_turn(turn1)
        conv.add_turn(turn2)

        conv.rollback_to_turn(turn2.turn_id)

        assert len(conv.last_episode.turns) == 2

    def test_rollback_removes_episodes_after_target(self):
        conv = Conversation()
        turn1 = make_turn("1")
        conv.add_turn(turn1)
        # Archive to create a second episode
        conv.archive_turns(1, "Summary", "Prefix")
        # Now add a turn to the new episode
        turn2 = make_turn("2")
        conv.add_turn(turn2)

        assert len(conv.episodes) == 2

        # Rollback to turn1 (in the first/finished episode)
        conv.rollback_to_turn(turn1.turn_id)

        # Should have only one episode now, and it should be unfinished
        assert len(conv.episodes) == 1
        assert conv.episodes[0].is_finished is False
        assert conv.episodes[0].episode_summary is None


# ---------------------------------------------------------------------------
# save / save_as / load / exists
# ---------------------------------------------------------------------------


class TestConversationSaveLoad:
    def test_save_raises_for_temporary_conversation(self):
        conv = Conversation()
        with pytest.raises(RuntimeError, match="Cant save temporary conversation"):
            conv.save()

    def test_save_creates_metadata_file(self, tmp_path):
        conv = Conversation(name="test")
        conv.storage_path = tmp_path
        conv.add_turn(make_turn("Hello"))

        # Need to set up episodes cache with path
        conv._episodes = FileMappedEpisodeCache(tmp_path, "test")
        conv.episodes.append(Episode())
        conv.add_turn(make_turn("Hello"))

        conv.save()

        assert (tmp_path / "test_metadata.json").is_file()

    def test_save_creates_episodes_file(self, tmp_path):
        conv = Conversation(name="test")
        conv._episodes = FileMappedEpisodeCache(tmp_path, "test")
        conv.episodes.append(Episode())
        conv.add_turn(make_turn("Hello"))
        conv.episodes.mark_dirty(0)
        conv.storage_path = tmp_path

        conv.save()

        assert (tmp_path / "test_episodes.json").is_file()

    def test_save_as_creates_files(self, tmp_path):
        conv = Conversation()
        conv.add_turn(make_turn("Hello"))

        conv.save_as("saved", tmp_path)

        assert (tmp_path / "saved_metadata.json").is_file()
        assert (tmp_path / "saved_episodes.json").is_file()

    def test_save_as_creates_parent_dirs(self, tmp_path):
        conv = Conversation()
        nested_path = tmp_path / "nested" / "dir"

        conv.save_as("test", nested_path)

        assert (nested_path / "test_metadata.json").is_file()
        assert (nested_path / "test_episodes.json").is_file()

    def test_load_roundtrip(self, tmp_path):
        # Create and save a conversation
        conv = Conversation(name="test", persona="assistant")
        conv.save_as("test", tmp_path)

        # Load it back
        loaded = Conversation.load("test", tmp_path)

        assert loaded.name == "test"
        assert loaded.persona == "assistant"
        assert loaded.storage_path == tmp_path
        assert len(loaded.episodes) >= 1  # At least the initial episode

    def test_load_preserves_turns(self, tmp_path):
        conv = Conversation(name="test")
        conv.add_turn(make_turn("Hello", "Hi"))
        conv.add_turn(make_turn("How are you?", "Good"))
        conv.save_as("test", tmp_path)

        loaded = Conversation.load("test", tmp_path)

        # Find the episode with turns
        turns_found = []
        for ep in loaded.episodes:
            turns_found.extend(ep.turns)
        assert len(turns_found) == 2

    def test_exists_returns_false_when_no_files(self, tmp_path):
        assert Conversation.exists("test", tmp_path) is False

    def test_exists_returns_true_when_saved(self, tmp_path):
        conv = Conversation(name="test")
        conv.save_as("test", tmp_path)
        assert Conversation.exists("test", tmp_path) is True

    def test_exists_returns_false_for_different_name(self, tmp_path):
        conv = Conversation(name="test")
        conv.save_as("test", tmp_path)
        assert Conversation.exists("other", tmp_path) is False


# ---------------------------------------------------------------------------
# move_to
# ---------------------------------------------------------------------------


class TestConversationMoveTo:
    def test_move_to_updates_name_and_path(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()

        conv = Conversation(name="old_name")
        conv.storage_path = old_dir
        conv._episodes = FileMappedEpisodeCache(old_dir, "old_name")
        conv.episodes.append(Episode())
        conv.add_turn(make_turn("Hello"))
        conv.episodes.mark_dirty(0)

        conv.move_to("new_name", new_dir)

        assert conv.name == "new_name"
        assert conv.storage_path == new_dir

    def test_move_to_creates_new_files(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()

        conv = Conversation(name="test")
        conv.storage_path = old_dir
        conv._episodes = FileMappedEpisodeCache(old_dir, "test")
        conv.episodes.append(Episode())
        conv.add_turn(make_turn("Hello"))
        conv.episodes.mark_dirty(0)
        conv.save()

        conv.move_to("moved", new_dir)

        assert (new_dir / "moved_metadata.json").is_file()
        assert (new_dir / "moved_episodes.json").is_file()

    def test_move_to_deletes_old_metadata(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()

        conv = Conversation(name="test")
        conv.storage_path = old_dir
        conv._episodes = FileMappedEpisodeCache(old_dir, "test")
        conv.episodes.append(Episode())
        conv.add_turn(make_turn("Hello"))
        conv.episodes.mark_dirty(0)
        conv.save()

        assert (old_dir / "test_metadata.json").exists()

        conv.move_to("moved", new_dir)

        assert not (old_dir / "test_metadata.json").exists()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestConversationSerialization:
    def test_model_dump_excludes_private_attrs(self):
        """Private attributes (_episodes, _data_path) should not be serialized."""
        conv = Conversation(name="test")
        data = conv.model_dump()
        assert "_episodes" not in data
        assert "_data_path" not in data

    def test_model_dump_includes_public_fields(self):
        conv = Conversation(name="test", persona="assistant")
        data = conv.model_dump()
        assert data["name"] == "test"
        assert data["persona"] == "assistant"

    def test_json_roundtrip(self, tmp_path):
        """Serialization roundtrip for metadata (episodes are separate)."""
        conv = Conversation(name="test", persona="assistant")
        conv.task_list = TaskList()
        conv.task_list.add_item("Do something")

        json_str = conv.model_dump_json()
        loaded = Conversation.model_validate_json(json_str)

        assert loaded.name == "test"
        assert loaded.persona == "assistant"
        assert loaded.task_list is not None
        assert len(loaded.task_list) == 1
