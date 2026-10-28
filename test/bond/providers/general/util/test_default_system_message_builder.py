"""Tests for bond.providers.general.util.default_system_message_builder module."""

from bond.conversation.conversation import Conversation
from bond.conversation.task_list import TaskList, TaskListItem
from bond.conversation.types import SystemMessage, TextChunk
from bond.conversation.working_set import WorkingSet
from bond.conversation.working_set_item import TextItem
from bond.providers.general.util.default_system_message_builder import (
    DefaultSystemMessageBuilder,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_conversation_with_prefix_summary(
    prefix_summary: str | None = "Previous context summary",
) -> Conversation:
    """Create a conversation with a prefix summary on the last episode."""
    conv = Conversation()
    # Access last_episode to initialize it, then set prefix_summary
    episode = conv.last_episode
    episode.prefix_summary = prefix_summary
    return conv


def make_conversation_with_working_set(
    items: list[str] | None = None,
) -> Conversation:
    """Create a conversation with a working set containing text items."""
    conv = Conversation()
    working_set = WorkingSet()
    for item_text in items or ["Item 1", "Item 2"]:
        working_set.add_item(TextItem(text=item_text))
    conv.working_set = working_set
    return conv


def make_conversation_with_task_list(
    items: list[tuple[str, bool]] | None = None,
) -> Conversation:
    """Create a conversation with a task list.

    Args:
        items: List of (description, is_complete) tuples.
    """
    conv = Conversation()
    task_list = TaskList()
    for desc, complete in items or [("Task 1", False), ("Task 2", True)]:
        item = TaskListItem(index=len(task_list), description=desc, is_complete=complete)
        task_list.content.append(item)
    conv.task_list = task_list
    return conv


def make_full_conversation(
    prefix_summary: str | None = "Previous context",
    working_set_items: list[str] | None = None,
    task_list_items: list[tuple[str, bool]] | None = None,
) -> Conversation:
    """Create a conversation with all context elements."""
    conv = make_conversation_with_prefix_summary(prefix_summary)
    conv.working_set = WorkingSet()
    for item_text in working_set_items or ["Working item 1"]:
        conv.working_set.add_item(TextItem(text=item_text))
    conv.task_list = TaskList()
    for desc, complete in task_list_items or [("Task 1", False)]:
        item = TaskListItem(
            index=len(conv.task_list), description=desc, is_complete=complete
        )
        conv.task_list.content.append(item)
    return conv


# ---------------------------------------------------------------------------
# DefaultSystemMessageBuilder - initialization
# ---------------------------------------------------------------------------


class TestDefaultSystemMessageBuilderInit:
    def test_default_parameters(self):
        builder = DefaultSystemMessageBuilder()
        assert builder._include_prefix_summary is False
        assert builder._include_working_set is False
        assert builder._include_task_list is False

    def test_include_prefix_summary(self):
        builder = DefaultSystemMessageBuilder(include_prefix_summary=True)
        assert builder._include_prefix_summary is True
        assert builder._include_working_set is False
        assert builder._include_task_list is False

    def test_include_working_set(self):
        builder = DefaultSystemMessageBuilder(include_working_set=True)
        assert builder._include_prefix_summary is False
        assert builder._include_working_set is True
        assert builder._include_task_list is False

    def test_include_task_list(self):
        builder = DefaultSystemMessageBuilder(include_task_list=True)
        assert builder._include_prefix_summary is False
        assert builder._include_working_set is False
        assert builder._include_task_list is True

    def test_all_parameters(self):
        builder = DefaultSystemMessageBuilder(
            include_prefix_summary=True,
            include_working_set=True,
            include_task_list=True,
        )
        assert builder._include_prefix_summary is True
        assert builder._include_working_set is True
        assert builder._include_task_list is True


# ---------------------------------------------------------------------------
# DefaultSystemMessageBuilder - basic behavior
# ---------------------------------------------------------------------------


class TestRenderSystemMessageBasic:
    def test_prompt_only_returns_system_message(self):
        builder = DefaultSystemMessageBuilder()
        conv = Conversation()
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert isinstance(result, SystemMessage)
        assert result.role == "system"
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextChunk)
        assert result.content[0].text == "You are helpful"

    def test_none_prompt_returns_none(self):
        builder = DefaultSystemMessageBuilder()
        conv = Conversation()
        result = builder.render_system_message(conv, None)
        assert result is None

    def test_empty_prompt_returns_system_message(self):
        builder = DefaultSystemMessageBuilder()
        conv = Conversation()
        result = builder.render_system_message(conv, "")
        assert result is not None
        assert result.content[0].text == ""

    def test_returns_system_message_type(self):
        builder = DefaultSystemMessageBuilder()
        conv = Conversation()
        result = builder.render_system_message(conv, "prompt")
        assert isinstance(result, SystemMessage)


# ---------------------------------------------------------------------------
# DefaultSystemMessageBuilder - prefix summary
# ---------------------------------------------------------------------------


class TestRenderSystemMessagePrefixSummary:
    def test_include_prefix_summary_with_summary(self):
        builder = DefaultSystemMessageBuilder(include_prefix_summary=True)
        conv = make_conversation_with_prefix_summary("Previous context summary")
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        text = result.content[0].text
        assert "You are helpful" in text
        assert "<previous-context>" in text
        assert "Previous context summary" in text
        assert "</previous-context>" in text
        # Prompt should come first, then context
        assert text.index("You are helpful") < text.index("<previous-context>")

    def test_include_prefix_summary_without_summary(self):
        """If enabled but no prefix_summary, should just return prompt."""
        builder = DefaultSystemMessageBuilder(include_prefix_summary=True)
        conv = make_conversation_with_prefix_summary(None)
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_prefix_summary_without_prompt(self):
        """If enabled and has summary but no prompt, should return just context."""
        builder = DefaultSystemMessageBuilder(include_prefix_summary=True)
        conv = make_conversation_with_prefix_summary("Previous context")
        result = builder.render_system_message(conv, None)
        assert result is not None
        text = result.content[0].text
        assert "<previous-context>" in text
        assert "Previous context" in text

    def test_prefix_summary_disabled_ignores_summary(self):
        """If disabled, should ignore prefix_summary even if present."""
        builder = DefaultSystemMessageBuilder(include_prefix_summary=False)
        conv = make_conversation_with_prefix_summary("Previous context")
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_prefix_summary_includes_metadata(self):
        builder = DefaultSystemMessageBuilder(include_prefix_summary=True)
        conv = make_conversation_with_prefix_summary("Summary")
        result = builder.render_system_message(conv, "prompt")
        text = result.content[0].text
        assert "<reliability>imperfect</reliability>" in text
        assert "<source>model generated</source>" in text
        assert "<content>" in text


# ---------------------------------------------------------------------------
# DefaultSystemMessageBuilder - working set
# ---------------------------------------------------------------------------


class TestRenderSystemMessageWorkingSet:
    def test_include_working_set_with_items(self):
        builder = DefaultSystemMessageBuilder(include_working_set=True)
        conv = make_conversation_with_working_set(["Item 1", "Item 2"])
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        text = result.content[0].text
        assert "You are helpful" in text
        assert "<working-set>" in text
        assert "Item 1" in text
        assert "Item 2" in text
        assert "</working-set>" in text

    def test_include_working_set_without_working_set(self):
        """If enabled but no working_set, should just return prompt."""
        builder = DefaultSystemMessageBuilder(include_working_set=True)
        conv = Conversation()
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_include_working_set_empty(self):
        """If enabled but working set is empty, should just return prompt."""
        builder = DefaultSystemMessageBuilder(include_working_set=True)
        conv = Conversation()
        conv.working_set = WorkingSet()  # Empty working set
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_working_set_without_prompt(self):
        """If enabled and has items but no prompt, should return just context."""
        builder = DefaultSystemMessageBuilder(include_working_set=True)
        conv = make_conversation_with_working_set(["Item 1"])
        result = builder.render_system_message(conv, None)
        assert result is not None
        text = result.content[0].text
        assert "<working-set>" in text
        assert "Item 1" in text

    def test_working_set_disabled_ignores_items(self):
        """If disabled, should ignore working set even if present."""
        builder = DefaultSystemMessageBuilder(include_working_set=False)
        conv = make_conversation_with_working_set(["Item 1"])
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_working_set_includes_metadata(self):
        builder = DefaultSystemMessageBuilder(include_working_set=True)
        conv = make_conversation_with_working_set(["Item 1"])
        result = builder.render_system_message(conv, "prompt")
        text = result.content[0].text
        assert "<reliability>potentially outdated</reliability>" in text
        assert "<source>updated during summarization</source>" in text
        assert "<content>" in text

    def test_working_set_renders_items_with_index(self):
        builder = DefaultSystemMessageBuilder(include_working_set=True)
        conv = make_conversation_with_working_set(["First item", "Second item"])
        result = builder.render_system_message(conv, "prompt")
        text = result.content[0].text
        assert '<item index=0>' in text
        assert '<item index=1>' in text


# ---------------------------------------------------------------------------
# DefaultSystemMessageBuilder - task list
# ---------------------------------------------------------------------------


class TestRenderSystemMessageTaskList:
    def test_include_task_list_with_items(self):
        builder = DefaultSystemMessageBuilder(include_task_list=True)
        conv = make_conversation_with_task_list(
            [("Task 1", False), ("Task 2", True)]
        )
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        text = result.content[0].text
        assert "You are helpful" in text
        assert "<task-list>" in text
        assert "Task 1" in text
        assert "Task 2" in text
        assert "</task-list>" in text

    def test_include_task_list_without_task_list(self):
        """If enabled but no task_list, should just return prompt."""
        builder = DefaultSystemMessageBuilder(include_task_list=True)
        conv = Conversation()
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_include_task_list_empty(self):
        """If enabled but task list is empty, should just return prompt."""
        builder = DefaultSystemMessageBuilder(include_task_list=True)
        conv = Conversation()
        conv.task_list = TaskList()  # Empty task list
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_task_list_without_prompt(self):
        """If enabled and has items but no prompt, should return just context."""
        builder = DefaultSystemMessageBuilder(include_task_list=True)
        conv = make_conversation_with_task_list([("Task 1", False)])
        result = builder.render_system_message(conv, None)
        assert result is not None
        text = result.content[0].text
        assert "<task-list>" in text
        assert "Task 1" in text

    def test_task_list_disabled_ignores_items(self):
        """If disabled, should ignore task list even if present."""
        builder = DefaultSystemMessageBuilder(include_task_list=False)
        conv = make_conversation_with_task_list([("Task 1", False)])
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_task_list_includes_metadata(self):
        builder = DefaultSystemMessageBuilder(include_task_list=True)
        conv = make_conversation_with_task_list([("Task 1", False)])
        result = builder.render_system_message(conv, "prompt")
        text = result.content[0].text
        assert "<reliability>imperfect</reliability>" in text
        assert "<source>self-maintained</source>" in text
        assert "<content>" in text

    def test_task_list_renders_completion_status(self):
        builder = DefaultSystemMessageBuilder(include_task_list=True)
        conv = make_conversation_with_task_list(
            [("Incomplete task", False), ("Complete task", True)]
        )
        result = builder.render_system_message(conv, "prompt")
        text = result.content[0].text
        assert "[ ] Incomplete task" in text
        assert "[x] Complete task" in text


# ---------------------------------------------------------------------------
# DefaultSystemMessageBuilder - combined context
# ---------------------------------------------------------------------------


class TestRenderSystemMessageCombined:
    def test_all_sections_combined(self):
        """Test that all context sections are combined correctly."""
        builder = DefaultSystemMessageBuilder(
            include_prefix_summary=True,
            include_working_set=True,
            include_task_list=True,
        )
        conv = make_full_conversation(
            prefix_summary="Previous context",
            working_set_items=["Working item"],
            task_list_items=[("Task 1", False)],
        )
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        text = result.content[0].text

        # All sections should be present
        assert "You are helpful" in text
        assert "<working-set>" in text
        assert "Working item" in text
        assert "<task-list>" in text
        assert "Task 1" in text
        assert "<previous-context>" in text
        assert "Previous context" in text

        # Prompt should come first
        assert text.index("You are helpful") < text.index("<working-set>")
        assert text.index("You are helpful") < text.index("<task-list>")
        assert text.index("You are helpful") < text.index("<previous-context>")

    def test_section_order(self):
        """Test that sections appear in the correct order: working-set, task-list, previous-context."""
        builder = DefaultSystemMessageBuilder(
            include_prefix_summary=True,
            include_working_set=True,
            include_task_list=True,
        )
        conv = make_full_conversation(
            prefix_summary="Previous",
            working_set_items=["WS item"],
            task_list_items=[("TL item", False)],
        )
        result = builder.render_system_message(conv, "prompt")
        text = result.content[0].text

        # Order: working-set, task-list, previous-context
        ws_idx = text.index("<working-set>")
        tl_idx = text.index("<task-list>")
        pc_idx = text.index("<previous-context>")
        assert ws_idx < tl_idx < pc_idx

    def test_prompt_and_context_separated_by_newlines(self):
        """Prompt and context should be separated by double newline."""
        builder = DefaultSystemMessageBuilder(include_prefix_summary=True)
        conv = make_conversation_with_prefix_summary("Summary")
        result = builder.render_system_message(conv, "You are helpful")
        text = result.content[0].text
        assert "You are helpful\n\n<previous-context>" in text

    def test_only_prompt_and_no_context_sections(self):
        """When no context is included, should just be the prompt."""
        builder = DefaultSystemMessageBuilder()
        conv = make_full_conversation()
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_no_prompt_and_no_context_returns_none(self):
        """When no prompt and no context sections are included, returns None."""
        builder = DefaultSystemMessageBuilder()
        conv = make_full_conversation()
        result = builder.render_system_message(conv, None)
        assert result is None

    def test_partial_context_without_prompt(self):
        """Test context sections without a prompt."""
        builder = DefaultSystemMessageBuilder(
            include_working_set=True,
            include_task_list=True,
        )
        conv = make_conversation_with_working_set(["WS item"])
        conv.task_list = TaskList()
        conv.task_list.add_item("TL item")
        result = builder.render_system_message(conv, None)
        assert result is not None
        text = result.content[0].text
        assert "<working-set>" in text
        assert "<task-list>" in text
        # Should be joined with newline
        assert "</working-set>\n<task-list>" in text


# ---------------------------------------------------------------------------
# DefaultSystemMessageBuilder - edge cases
# ---------------------------------------------------------------------------


class TestDefaultSystemMessageBuilderEdgeCases:
    def test_empty_conversation_with_all_options(self):
        """Empty conversation with all options enabled and no prompt."""
        builder = DefaultSystemMessageBuilder(
            include_prefix_summary=True,
            include_working_set=True,
            include_task_list=True,
        )
        conv = Conversation()
        result = builder.render_system_message(conv, None)
        assert result is None

    def test_empty_conversation_with_prompt(self):
        """Empty conversation with all options enabled but with prompt."""
        builder = DefaultSystemMessageBuilder(
            include_prefix_summary=True,
            include_working_set=True,
            include_task_list=True,
        )
        conv = Conversation()
        result = builder.render_system_message(conv, "You are helpful")
        assert result is not None
        assert result.content[0].text == "You are helpful"

    def test_special_characters_in_prompt(self):
        """Test that special characters in prompt are preserved."""
        builder = DefaultSystemMessageBuilder()
        conv = Conversation()
        prompt = 'You are a "helpful" <assistant> & friend'
        result = builder.render_system_message(conv, prompt)
        assert result is not None
        assert result.content[0].text == prompt

    def test_multiline_prompt(self):
        """Test that multiline prompts are preserved."""
        builder = DefaultSystemMessageBuilder()
        conv = Conversation()
        prompt = "Line 1\nLine 2\nLine 3"
        result = builder.render_system_message(conv, prompt)
        assert result is not None
        assert result.content[0].text == prompt
