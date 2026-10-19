"""Tests for bond.conversation.cache.file_mapped module."""

import json

import pytest

from bond.conversation.cache.file_mapped import FileMappedEpisodeCache
from bond.conversation.cache.temporary import TemporaryEpisodeCache
from bond.conversation.types import (
    AssistantConversationMessage,
    AssistantMessage,
    Episode,
    TextChunk,
    Turn,
    UsageInfo,
    UserConversationMessage,
    UserMessage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_episode(
    prefix_summary: str | None = None,
    episode_summary: str | None = None,
    turns: list[Turn] | None = None,
) -> Episode:
    return Episode(
        prefix_summary=prefix_summary,
        episode_summary=episode_summary,
        turns=turns or [],
    )


def make_turn(user_text: str = "Hello", assistant_text: str = "Hi") -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create(user_text),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(content=[TextChunk(text=assistant_text)]),
            name="assistant",
            usage=UsageInfo(completion_tokens=5, prompt_tokens=10, total_tokens=15),
        ),
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestFileMappedCacheInit:
    def test_init_both_none(self):
        """Temporary cache: both base_path and name are None."""
        cache = FileMappedEpisodeCache(None, None)
        assert len(cache) == 0

    def test_init_with_path_and_name(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test")
        assert len(cache) == 0

    def test_init_with_episodes(self, tmp_path):
        episodes = [make_episode(), make_episode()]
        cache = FileMappedEpisodeCache(tmp_path, "test", episodes)
        assert len(cache) == 2

    def test_init_only_base_path_raises(self, tmp_path):
        """base_path without name should raise."""
        with pytest.raises(ValueError, match="both be set or both be None"):
            FileMappedEpisodeCache(tmp_path, None)  # type: ignore

    def test_init_only_name_raises(self):
        """name without base_path should raise."""
        with pytest.raises(ValueError, match="both be set or both be None"):
            FileMappedEpisodeCache(None, "test")  # type: ignore

    def test_init_not_dirty_by_default(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test")
        assert cache._dirty is False

    def test_is_temporary_episode_cache(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test")
        assert isinstance(cache, TemporaryEpisodeCache)


# ---------------------------------------------------------------------------
# mark_dirty
# ---------------------------------------------------------------------------


class TestFileMappedCacheMarkDirty:
    def test_mark_dirty_sets_flag(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test")
        assert cache._dirty is False
        cache.mark_dirty(0)
        assert cache._dirty is True

    def test_mark_dirty_multiple_times(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode(), make_episode()])
        cache.mark_dirty(0)
        cache.mark_dirty(1)
        assert cache._dirty is True


# ---------------------------------------------------------------------------
# save_as
# ---------------------------------------------------------------------------


class TestFileMappedCacheSaveAs:
    def test_save_as_creates_file(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode()])
        cache.save_as("my_cache", tmp_path)
        assert (tmp_path / "my_cache_episodes.json").is_file()

    def test_save_as_creates_parent_directories(self, tmp_path):
        """save_as should create parent directories if they don't exist."""
        nested_path = tmp_path / "nested" / "dir"
        cache = FileMappedEpisodeCache(None, None, [make_episode()])
        cache.save_as("test", nested_path)
        assert (nested_path / "test_episodes.json").is_file()

    def test_save_as_writes_correct_content(self, tmp_path):
        episodes = [
            make_episode(prefix_summary="Summary 1"),
            make_episode(episode_summary="Finished"),
        ]
        cache = FileMappedEpisodeCache(None, None, episodes)
        cache.save_as("test", tmp_path)

        file_path = tmp_path / "test_episodes.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["prefix_summary"] == "Summary 1"
        assert data[1]["episode_summary"] == "Finished"

    def test_save_as_empty_cache(self, tmp_path):
        cache = FileMappedEpisodeCache(None, None)
        cache.save_as("empty", tmp_path)
        file_path = tmp_path / "empty_episodes.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data == []

    def test_save_as_with_turns(self, tmp_path):
        turn = make_turn("Hello", "Hi there")
        episode = make_episode(turns=[turn])
        cache = FileMappedEpisodeCache(None, None, [episode])
        cache.save_as("test", tmp_path)

        file_path = tmp_path / "test_episodes.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert len(data[0]["turns"]) == 1

    def test_save_as_does_not_set_dirty(self, tmp_path):
        """save_as should not modify the dirty flag."""
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode()])
        assert cache._dirty is False
        cache.save_as("other", tmp_path)
        assert cache._dirty is False


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


class TestFileMappedCacheSave:
    def test_save_writes_file_when_dirty(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode()])
        cache.mark_dirty(0)
        cache.save()
        assert (tmp_path / "test_episodes.json").is_file()

    def test_save_does_nothing_when_not_dirty(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode()])
        cache.save()
        # File should NOT be created because cache is not dirty
        assert not (tmp_path / "test_episodes.json").exists()

    def test_save_raises_when_dirty_but_no_path(self):
        """If dirty but no path set, save should raise RuntimeError."""
        cache = FileMappedEpisodeCache(None, None, [make_episode()])
        cache.mark_dirty(0)
        with pytest.raises(RuntimeError, match="Cannot save temporary cache"):
            cache.save()

    def test_save_clears_dirty_after_save_as(self, tmp_path):
        """Note: save() calls save_as() which doesn't clear dirty.
        This tests the actual behavior."""
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode()])
        cache.mark_dirty(0)
        cache.save()
        # The current implementation doesn't clear _dirty after save
        # This test documents the actual behavior
        assert (tmp_path / "test_episodes.json").is_file()


# ---------------------------------------------------------------------------
# load (classmethod)
# ---------------------------------------------------------------------------


class TestFileMappedCacheLoad:
    def test_load_existing_file(self, tmp_path):
        # Create a cache and save it
        episodes = [make_episode(prefix_summary="Test")]
        cache = FileMappedEpisodeCache(tmp_path, "test", episodes)
        cache.save_as("test", tmp_path)

        # Load it back
        loaded = FileMappedEpisodeCache.load("test", tmp_path)
        assert len(loaded) == 1
        assert loaded[0].prefix_summary == "Test"

    def test_load_sets_path_and_name(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode()])
        cache.save_as("test", tmp_path)

        loaded = FileMappedEpisodeCache.load("test", tmp_path)
        assert loaded._name == "test"
        assert loaded._base_path == tmp_path

    def test_load_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="is not a file"):
            FileMappedEpisodeCache.load("nonexistent", tmp_path)

    def test_load_multiple_episodes(self, tmp_path):
        episodes = [
            make_episode(prefix_summary="First"),
            make_episode(episode_summary="Second"),
            make_episode(prefix_summary="Third", episode_summary="Done"),
        ]
        cache = FileMappedEpisodeCache(tmp_path, "test", episodes)
        cache.save_as("test", tmp_path)

        loaded = FileMappedEpisodeCache.load("test", tmp_path)
        assert len(loaded) == 3
        assert loaded[0].prefix_summary == "First"
        assert loaded[1].episode_summary == "Second"
        assert loaded[2].prefix_summary == "Third"
        assert loaded[2].episode_summary == "Done"

    def test_load_empty_file(self, tmp_path):
        # Create an empty episodes file
        file_path = tmp_path / "empty_episodes.json"
        file_path.write_text("[]", encoding="utf-8")

        loaded = FileMappedEpisodeCache.load("empty", tmp_path)
        assert len(loaded) == 0

    def test_load_with_turns(self, tmp_path):
        turn = make_turn("User message", "Assistant response")
        episode = make_episode(turns=[turn])
        cache = FileMappedEpisodeCache(tmp_path, "test", [episode])
        cache.save_as("test", tmp_path)

        loaded = FileMappedEpisodeCache.load("test", tmp_path)
        assert len(loaded) == 1
        assert len(loaded[0].turns) == 1
        assert loaded[0].turns[0].user_message is not None
        assert loaded[0].turns[0].user_message.message.content[0].text == "User message"


# ---------------------------------------------------------------------------
# exists (classmethod)
# ---------------------------------------------------------------------------


class TestFileMappedCacheExists:
    def test_exists_returns_true_when_file_exists(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode()])
        cache.save_as("test", tmp_path)
        assert FileMappedEpisodeCache.exists("test", tmp_path) is True

    def test_exists_returns_false_when_file_missing(self, tmp_path):
        assert FileMappedEpisodeCache.exists("nonexistent", tmp_path) is False

    def test_exists_returns_false_for_empty_dir(self, tmp_path):
        assert FileMappedEpisodeCache.exists("anything", tmp_path) is False


# ---------------------------------------------------------------------------
# move_to
# ---------------------------------------------------------------------------


class TestFileMappedCacheMoveTo:
    def test_move_to_new_location(self, tmp_path):
        """Move cache from one location to another."""
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()

        cache = FileMappedEpisodeCache(old_dir, "test", [make_episode()])
        cache.mark_dirty(0)
        cache.save()

        # Move to new location
        cache.move_to("renamed", new_dir)

        # New file should exist
        assert (new_dir / "renamed_episodes.json").is_file()
        # Old file should be deleted
        assert not (old_dir / "test_episodes.json").exists()
        # Internal state updated
        assert cache._name == "renamed"
        assert cache._base_path == new_dir

    def test_move_to_from_temporary(self, tmp_path):
        """Move a temporary cache (no path) to a real location."""
        cache = FileMappedEpisodeCache(None, None, [make_episode()])
        cache.mark_dirty(0)

        cache.move_to("test", tmp_path)

        assert (tmp_path / "test_episodes.json").is_file()
        assert cache._name == "test"
        assert cache._base_path == tmp_path

    def test_move_to_preserves_episodes(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()

        episodes = [
            make_episode(prefix_summary="First"),
            make_episode(episode_summary="Second"),
        ]
        cache = FileMappedEpisodeCache(old_dir, "test", episodes)
        cache.mark_dirty(0)
        cache.save()

        cache.move_to("moved", new_dir)

        # Load from new location and verify
        loaded = FileMappedEpisodeCache.load("moved", new_dir)
        assert len(loaded) == 2
        assert loaded[0].prefix_summary == "First"
        assert loaded[1].episode_summary == "Second"

    def test_move_to_same_name_different_dir(self, tmp_path):
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()

        cache = FileMappedEpisodeCache(old_dir, "test", [make_episode()])
        cache.mark_dirty(0)
        cache.save()

        cache.move_to("test", new_dir)

        assert (new_dir / "test_episodes.json").is_file()
        assert not (old_dir / "test_episodes.json").exists()


# ---------------------------------------------------------------------------
# Round-trip: save -> load
# ---------------------------------------------------------------------------


class TestFileMappedCacheRoundTrip:
    def test_roundtrip_preserves_episodes(self, tmp_path):
        episodes = [
            make_episode(prefix_summary="Context"),
            make_episode(turns=[make_turn("Hello", "Hi")]),
            make_episode(episode_summary="Done"),
        ]
        cache = FileMappedEpisodeCache(tmp_path, "test", episodes)
        cache.mark_dirty(0)
        cache.save()

        loaded = FileMappedEpisodeCache.load("test", tmp_path)
        assert len(loaded) == 3
        assert loaded[0].prefix_summary == "Context"
        assert loaded[1].turns[0].user_message.message.content[0].text == "Hello"
        assert loaded[2].episode_summary == "Done"

    def test_roundtrip_empty_cache(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test")
        cache.save_as("test", tmp_path)

        loaded = FileMappedEpisodeCache.load("test", tmp_path)
        assert len(loaded) == 0

    def test_roundtrip_after_modifications(self, tmp_path):
        """Save, modify, save again, load - should get latest state."""
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode(prefix_summary="v1")])
        cache.save_as("test", tmp_path)

        # Modify
        cache.append(make_episode(prefix_summary="v2"))
        cache.save_as("test", tmp_path)

        loaded = FileMappedEpisodeCache.load("test", tmp_path)
        assert len(loaded) == 2
        assert loaded[0].prefix_summary == "v1"
        assert loaded[1].prefix_summary == "v2"


# ---------------------------------------------------------------------------
# Inherited operations still work
# ---------------------------------------------------------------------------


class TestFileMappedCacheInheritedOps:
    """Sanity checks that inherited TemporaryEpisodeCache methods still work."""

    def test_append_works(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test")
        cache.append(make_episode())
        assert len(cache) == 1

    def test_getitem_works(self, tmp_path):
        ep = make_episode(prefix_summary="Test")
        cache = FileMappedEpisodeCache(tmp_path, "test", [ep])
        assert cache[0].prefix_summary == "Test"

    def test_truncate_works(self, tmp_path):
        cache = FileMappedEpisodeCache(tmp_path, "test", [make_episode(), make_episode()])
        cache.truncate(1)
        assert len(cache) == 1

    def test_add_turn_works(self, tmp_path):
        ep = make_episode()
        cache = FileMappedEpisodeCache(tmp_path, "test", [ep])
        cache.add_turn(make_turn())
        assert len(ep.turns) == 1

    def test_last_property_works(self, tmp_path):
        ep1, ep2 = make_episode(), make_episode()
        cache = FileMappedEpisodeCache(tmp_path, "test", [ep1, ep2])
        assert cache.last is ep2
