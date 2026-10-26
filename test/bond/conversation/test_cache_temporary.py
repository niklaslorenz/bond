"""Tests for bond.conversation.cache.temporary module."""

import pytest
from returns.result import Failure

from bond.conversation.cache.base import EpisodeCache
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


def make_episode(turns: list[Turn] | None = None) -> Episode:
    return Episode(turns=turns or [])


def make_turn(user_text: str = "Hello") -> Turn:
    return Turn(
        user_message=UserConversationMessage(
            message=UserMessage.create(user_text),
            name="user",
        ),
        assistant_response=AssistantConversationMessage(
            message=AssistantMessage(content=[TextChunk(text="Hi")]),
            name="assistant",
        ),
        usage=UsageInfo(completion_tokens=5, prompt_tokens=10, total_tokens=15),
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestTemporaryCacheInit:
    def test_init_default_empty(self):
        cache = TemporaryEpisodeCache()
        assert len(cache) == 0

    def test_init_with_none(self):
        cache = TemporaryEpisodeCache(None)
        assert len(cache) == 0

    def test_init_with_empty_list(self):
        cache = TemporaryEpisodeCache([])
        assert len(cache) == 0

    def test_init_with_episodes(self):
        episodes = [make_episode(), make_episode()]
        cache = TemporaryEpisodeCache(episodes)
        assert len(cache) == 2

    def test_init_copies_list(self):
        """The cache should copy the input list, not hold a reference."""
        episodes = [make_episode()]
        cache = TemporaryEpisodeCache(episodes)
        episodes.append(make_episode())
        assert len(cache) == 1

    def test_is_episode_cache(self):
        cache = TemporaryEpisodeCache()
        assert isinstance(cache, EpisodeCache)


# ---------------------------------------------------------------------------
# __len__
# ---------------------------------------------------------------------------


class TestTemporaryCacheLen:
    def test_len_empty(self):
        cache = TemporaryEpisodeCache()
        assert len(cache) == 0

    def test_len_with_episodes(self):
        cache = TemporaryEpisodeCache([make_episode(), make_episode(), make_episode()])
        assert len(cache) == 3


# ---------------------------------------------------------------------------
# __getitem__
# ---------------------------------------------------------------------------


class TestTemporaryCacheGetItem:
    def test_getitem_first(self):
        ep1, ep2 = make_episode(), make_episode()
        cache = TemporaryEpisodeCache([ep1, ep2])
        assert cache[0] is ep1

    def test_getitem_second(self):
        ep1, ep2 = make_episode(), make_episode()
        cache = TemporaryEpisodeCache([ep1, ep2])
        assert cache[1] is ep2

    def test_getitem_negative_index(self):
        ep1, ep2, ep3 = make_episode(), make_episode(), make_episode()
        cache = TemporaryEpisodeCache([ep1, ep2, ep3])
        assert cache[-1] is ep3
        assert cache[-2] is ep2

    def test_getitem_slice(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        result = cache[1:3]
        assert len(result) == 2
        assert result[0] is episodes[1]
        assert result[1] is episodes[2]

    def test_getitem_slice_all(self):
        episodes = [make_episode() for _ in range(3)]
        cache = TemporaryEpisodeCache(episodes)
        result = cache[:]
        assert len(result) == 3

    def test_getitem_out_of_bounds_raises(self):
        cache = TemporaryEpisodeCache([make_episode()])
        with pytest.raises(IndexError):
            _ = cache[5]


# ---------------------------------------------------------------------------
# __setitem__
# ---------------------------------------------------------------------------


class TestTemporaryCacheSetItem:
    def test_setitem_int(self):
        ep1, ep2, ep3 = make_episode(), make_episode(), make_episode()
        cache = TemporaryEpisodeCache([ep1, ep2])
        cache[0] = ep3
        assert cache[0] is ep3
        assert cache[1] is ep2

    def test_setitem_int_wrong_type_raises(self):
        cache = TemporaryEpisodeCache([make_episode()])
        with pytest.raises(ValueError, match="Expected Episode"):
            cache[0] = "not an episode"  # type: ignore

    def test_setitem_slice(self):
        ep1, ep2, ep3, ep4 = (
            make_episode(),
            make_episode(),
            make_episode(),
            make_episode(),
        )
        cache = TemporaryEpisodeCache([ep1, ep2, ep3])
        cache[0:2] = [ep4]
        assert len(cache) == 2
        assert cache[0] is ep4
        assert cache[1] is ep3

    def test_setitem_slice_wrong_type_raises(self):
        """Slice assignment requires a list, not a single Episode."""
        cache = TemporaryEpisodeCache([make_episode(), make_episode()])
        with pytest.raises(ValueError, match="Expected list"):
            cache[0:1] = make_episode()  # type: ignore


# ---------------------------------------------------------------------------
# __iter__ (from base class)
# ---------------------------------------------------------------------------


class TestTemporaryCacheIter:
    def test_iter_empty(self):
        cache = TemporaryEpisodeCache()
        assert list(cache) == []

    def test_iter_with_episodes(self):
        episodes = [make_episode() for _ in range(3)]
        cache = TemporaryEpisodeCache(episodes)
        result = list(cache)
        assert len(result) == 3
        assert result == episodes


# ---------------------------------------------------------------------------
# iterate() (from base class)
# ---------------------------------------------------------------------------


class TestTemporaryCacheIterate:
    def test_iterate_all(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        result = list(cache.iterate())
        assert result == episodes

    def test_iterate_with_start(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        result = list(cache.iterate(start=2))
        assert len(result) == 3
        assert result[0] is episodes[2]

    def test_iterate_with_stop(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        result = list(cache.iterate(stop=2))
        assert len(result) == 2
        assert result[0] is episodes[0]
        assert result[1] is episodes[1]

    def test_iterate_with_start_and_stop(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        result = list(cache.iterate(start=1, stop=4))
        assert len(result) == 3
        assert result[0] is episodes[1]
        assert result[2] is episodes[3]

    def test_iterate_negative_start(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        result = list(cache.iterate(start=-2))
        assert len(result) == 2
        assert result[0] is episodes[3]

    def test_iterate_negative_stop(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        result = list(cache.iterate(stop=-1))
        assert len(result) == 4

    def test_iterate_stop_less_than_start_returns_empty(self):
        cache = TemporaryEpisodeCache([make_episode(), make_episode()])
        result = list(cache.iterate(start=1, stop=0))
        assert result == []


# ---------------------------------------------------------------------------
# last property (from base class)
# ---------------------------------------------------------------------------


class TestTemporaryCacheLast:
    def test_last_empty_returns_none(self):
        cache = TemporaryEpisodeCache()
        assert cache.last is None

    def test_last_with_episodes(self):
        ep1, ep2, ep3 = make_episode(), make_episode(), make_episode()
        cache = TemporaryEpisodeCache([ep1, ep2, ep3])
        assert cache.last is ep3

    def test_last_single_episode(self):
        ep = make_episode()
        cache = TemporaryEpisodeCache([ep])
        assert cache.last is ep


# ---------------------------------------------------------------------------
# add_turn (from base class)
# ---------------------------------------------------------------------------


class TestTemporaryCacheAddTurn:
    def test_add_turn_to_last_episode(self):
        ep = make_episode()
        cache = TemporaryEpisodeCache([ep])
        turn = make_turn("Test message")
        cache.add_turn(turn)
        assert len(ep.turns) == 1
        assert ep.turns[0] is turn

    def test_add_turn_to_correct_episode(self):
        ep1, ep2 = make_episode(), make_episode()
        cache = TemporaryEpisodeCache([ep1, ep2])
        turn = make_turn("Test")
        cache.add_turn(turn)
        # Should add to the last episode (ep2), not ep1
        assert len(ep1.turns) == 0
        assert len(ep2.turns) == 1

    def test_add_turn_no_episodes_raises(self):
        cache = TemporaryEpisodeCache()
        turn = make_turn()
        with pytest.raises(RuntimeError, match="No episode"):
            cache.add_turn(turn)


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------


class TestTemporaryCacheAppend:
    def test_append_to_empty(self):
        cache = TemporaryEpisodeCache()
        ep = make_episode()
        cache.append(ep)
        assert len(cache) == 1
        assert cache[0] is ep

    def test_append_to_non_empty(self):
        ep1, ep2 = make_episode(), make_episode()
        cache = TemporaryEpisodeCache([ep1])
        cache.append(ep2)
        assert len(cache) == 2
        assert cache[1] is ep2

    def test_append_multiple(self):
        cache = TemporaryEpisodeCache()
        for _ in range(5):
            cache.append(make_episode())
        assert len(cache) == 5


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------


class TestTemporaryCacheTruncate:
    def test_truncate_to_zero(self):
        cache = TemporaryEpisodeCache([make_episode(), make_episode()])
        cache.truncate(0)
        assert len(cache) == 0

    def test_truncate_to_smaller_length(self):
        episodes = [make_episode() for _ in range(5)]
        cache = TemporaryEpisodeCache(episodes)
        cache.truncate(2)
        assert len(cache) == 2
        assert cache[0] is episodes[0]
        assert cache[1] is episodes[1]

    def test_truncate_to_same_length(self):
        episodes = [make_episode() for _ in range(3)]
        cache = TemporaryEpisodeCache(episodes)
        cache.truncate(3)
        assert len(cache) == 3

    def test_truncate_to_larger_length_noop(self):
        """Truncating to a length >= current length should be a no-op."""
        episodes = [make_episode() for _ in range(3)]
        cache = TemporaryEpisodeCache(episodes)
        cache.truncate(10)
        assert len(cache) == 3

    def test_truncate_empty_cache(self):
        cache = TemporaryEpisodeCache()
        cache.truncate(0)
        assert len(cache) == 0


# ---------------------------------------------------------------------------
# mark_dirty (no-op in temporary cache)
# ---------------------------------------------------------------------------


class TestTemporaryCacheMarkDirty:
    def test_mark_dirty_is_noop(self):
        """mark_dirty should not raise any errors (it's a no-op)."""
        cache = TemporaryEpisodeCache([make_episode()])
        cache.mark_dirty(0)  # Should not raise

    def test_mark_dirty_multiple_indices(self):
        cache = TemporaryEpisodeCache([make_episode(), make_episode()])
        cache.mark_dirty(0)
        cache.mark_dirty(1)
        cache.mark_dirty(0)  # Duplicate should be fine


# ---------------------------------------------------------------------------
# save_as (returns Failure for temporary cache)
# ---------------------------------------------------------------------------


class TestTemporaryCacheSaveAs:
    def test_save_as_returns_failure(self, tmp_path):
        cache = TemporaryEpisodeCache([make_episode()])
        result = cache.save_as("test", tmp_path)
        assert isinstance(result, Failure)

    def test_save_as_failure_message(self, tmp_path):
        cache = TemporaryEpisodeCache()
        result = cache.save_as("test", tmp_path)
        assert isinstance(result, Failure)
        assert "cant save" in str(result.failure()).lower()

    def test_save_as_does_not_create_files(self, tmp_path):
        cache = TemporaryEpisodeCache([make_episode()])
        cache.save_as("test", tmp_path)
        # No files should be created
        assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# save (returns Failure for temporary cache)
# ---------------------------------------------------------------------------


class TestTemporaryCacheSave:
    def test_save_returns_failure(self):
        cache = TemporaryEpisodeCache([make_episode()])
        result = cache.save()
        assert isinstance(result, Failure)

    def test_save_failure_message(self):
        cache = TemporaryEpisodeCache()
        result = cache.save()
        assert isinstance(result, Failure)
        assert "cant save" in str(result.failure()).lower()

    def test_save_empty_cache_returns_failure(self):
        cache = TemporaryEpisodeCache()
        result = cache.save()
        assert isinstance(result, Failure)


# ---------------------------------------------------------------------------
# move_to (returns Failure for temporary cache)
# ---------------------------------------------------------------------------


class TestTemporaryCacheMoveTo:
    def test_move_to_returns_failure(self, tmp_path):
        cache = TemporaryEpisodeCache([make_episode()])
        result = cache.move_to("new_name", tmp_path)
        assert isinstance(result, Failure)

    def test_move_to_failure_message(self, tmp_path):
        cache = TemporaryEpisodeCache()
        result = cache.move_to("new_name", tmp_path)
        assert isinstance(result, Failure)
        assert "cant move" in str(result.failure()).lower()

    def test_move_to_does_not_create_files(self, tmp_path):
        cache = TemporaryEpisodeCache([make_episode()])
        cache.move_to("new_name", tmp_path)
        # No files should be created
        assert list(tmp_path.iterdir()) == []
