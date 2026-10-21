"""Tests for bond.tools.working_set module."""

from bond.conversation.conversation import Conversation
from bond.conversation.working_set import WorkingSet
from bond.conversation.working_set_item import (
    DirectoryReferenceItem,
    FileReferenceItem,
    TextItem,
)
from bond.tools.tool import ToolCallContext
from bond.tools.working_set import (
    add_working_set_directory,
    add_working_set_file,
    add_working_set_text,
    clear_working_set,
    remove_working_set_items,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_context(conversation: Conversation | None = None) -> ToolCallContext:
    """Create a minimal ToolCallContext with an optional conversation."""
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=None,
        logger=None,
        confirmation_prompt=None,
        conversation=conversation,
    )


def make_conversation_with_items(*items) -> Conversation:
    """Create a conversation with a working set containing the given items."""
    conv = Conversation()
    conv.working_set = WorkingSet()
    for item in items:
        conv.working_set.add_item(item)
    return conv


# ---------------------------------------------------------------------------
# add_working_set_text
# ---------------------------------------------------------------------------


class TestAddWorkingSetText:
    def test_add_text_item(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_working_set_text(context, text="Hello world")

        assert conv.working_set is not None
        assert len(conv.working_set) == 1
        assert isinstance((item := conv.working_set[0]), TextItem)
        assert item.text == "Hello world"
        assert isinstance(result, str)
        assert "Added text item" in result
        assert "Hello world" in result

    def test_add_to_existing_working_set(self):
        conv = make_conversation_with_items(TextItem(text="Existing"))
        context = make_context(conv)

        add_working_set_text(context, text="New item")

        assert conv.working_set is not None
        assert len(conv.working_set) == 2
        assert isinstance((item_0 := conv.working_set[0]), TextItem)
        assert isinstance((item_1 := conv.working_set[1]), TextItem)
        assert item_0.text == "Existing"
        assert item_1.text == "New item"

    def test_add_initializes_working_set_if_none(self):
        conv = Conversation()
        assert conv.working_set is None
        context = make_context(conv)

        add_working_set_text(context, text="First item")

        assert conv.working_set is not None
        assert len(conv.working_set) == 1

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = add_working_set_text(context, text="Test")

        assert isinstance(result, str)
        assert "Error" in result
        assert "No conversation context" in result

    def test_result_mentions_summarization(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_working_set_text(context, text="Test")

        assert isinstance(result, str)
        assert "summarization" in result.lower()

    def test_displayed_cache_not_updated(self):
        conv = Conversation()
        conv.working_set = WorkingSet()
        conv.working_set.update()
        initial_displayed = conv.working_set.displayed
        context = make_context(conv)

        add_working_set_text(context, text="New item")

        assert conv.working_set.displayed == initial_displayed

    def test_add_multiline_text(self):
        conv = Conversation()
        context = make_context(conv)
        text = "Line 1\nLine 2\nLine 3"

        add_working_set_text(context, text=text)

        assert conv.working_set is not None
        assert isinstance((item := conv.working_set[0]), TextItem)
        assert item.text == text


# ---------------------------------------------------------------------------
# add_working_set_file
# ---------------------------------------------------------------------------


class TestAddWorkingSetFile:
    def test_add_file_item(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_working_set_file(context, path="/path/to/file.py")

        assert conv.working_set is not None
        assert len(conv.working_set) == 1
        assert isinstance(item := conv.working_set[0], FileReferenceItem)
        assert item.path == "/path/to/file.py"
        assert isinstance(result, str)
        assert "Added file reference" in result
        assert "/path/to/file.py" in result

    def test_add_file_with_line_range(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_working_set_file(
            context, path="/file.py", start_line=10, end_line=20
        )

        assert conv.working_set is not None
        assert isinstance(item := conv.working_set[0], FileReferenceItem)
        assert item.start_line == 10
        assert item.end_line == 20
        assert isinstance(result, str)
        assert "lines 10-20" in result

    def test_add_file_with_start_line_only(self):
        conv = Conversation()
        context = make_context(conv)

        add_working_set_file(context, path="/file.py", start_line=5)

        assert conv.working_set is not None
        assert isinstance(item := conv.working_set[0], FileReferenceItem)
        assert item.start_line == 5
        assert item.end_line is None

    def test_add_file_initializes_working_set_if_none(self):
        conv = Conversation()
        context = make_context(conv)

        add_working_set_file(context, path="/file.py")

        assert conv.working_set is not None

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = add_working_set_file(context, path="/file.py")

        assert isinstance(result, str)
        assert "Error" in result

    def test_displayed_cache_not_updated(self):
        conv = Conversation()
        conv.working_set = WorkingSet()
        conv.working_set.update()
        initial_displayed = conv.working_set.displayed
        context = make_context(conv)

        add_working_set_file(context, path="/file.py")

        assert conv.working_set.displayed == initial_displayed


# ---------------------------------------------------------------------------
# add_working_set_directory
# ---------------------------------------------------------------------------


class TestAddWorkingSetDirectory:
    def test_add_directory_item(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_working_set_directory(context, path="/src", pattern="*.py")

        assert conv.working_set is not None
        assert len(conv.working_set) == 1
        assert isinstance(item := conv.working_set[0], DirectoryReferenceItem)
        assert item.path == "/src"
        assert item.pattern == "*.py"
        assert isinstance(result, str)
        assert "Added directory reference" in result

    def test_add_directory_with_options(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_working_set_directory(
            context,
            path="/src",
            pattern="*.txt",
            recursive=True,
            case_sensitive=False,
        )

        assert conv.working_set is not None
        assert isinstance(item := conv.working_set[0], DirectoryReferenceItem)
        assert item.recursive is True
        assert item.case_sensitive is False
        assert isinstance(result, str)
        assert "Recursive: True" in result
        assert "Case sensitive: False" in result

    def test_add_directory_default_options(self):
        conv = Conversation()
        context = make_context(conv)

        add_working_set_directory(context, path="/src", pattern="*.py")

        assert conv.working_set is not None
        assert isinstance(item := conv.working_set[0], DirectoryReferenceItem)
        assert item.recursive is False
        assert item.case_sensitive is True

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = add_working_set_directory(context, path="/src", pattern="*.py")

        assert isinstance(result, str)
        assert "Error" in result

    def test_displayed_cache_not_updated(self):
        conv = Conversation()
        conv.working_set = WorkingSet()
        conv.working_set.update()
        initial_displayed = conv.working_set.displayed
        context = make_context(conv)

        add_working_set_directory(context, path="/src", pattern="*.py")

        assert conv.working_set.displayed == initial_displayed


# ---------------------------------------------------------------------------
# remove_working_set_items
# ---------------------------------------------------------------------------


class TestRemoveWorkingSetItems:
    def test_remove_single_item(self):
        conv = make_conversation_with_items(
            TextItem(text="Item 1"),
            TextItem(text="Item 2"),
            TextItem(text="Item 3"),
        )
        context = make_context(conv)

        result = remove_working_set_items(context, indices=[1])

        assert conv.working_set is not None
        assert len(conv.working_set) == 2
        assert isinstance(item_0 := conv.working_set[0], TextItem)
        assert isinstance(item_1 := conv.working_set[1], TextItem)
        assert item_0.text == "Item 1"
        assert item_1.text == "Item 3"
        assert isinstance(result, str)
        assert "Removed 1 item(s)" in result

    def test_remove_multiple_items(self):
        conv = make_conversation_with_items(
            TextItem(text="A"),
            TextItem(text="B"),
            TextItem(text="C"),
            TextItem(text="D"),
        )
        context = make_context(conv)

        result = remove_working_set_items(context, indices=[0, 2])

        assert conv.working_set is not None
        assert len(conv.working_set) == 2
        assert isinstance(item_0 := conv.working_set[0], TextItem)
        assert isinstance(item_1 := conv.working_set[1], TextItem)
        assert item_0.text == "B"
        assert item_1.text == "D"
        assert isinstance(result, str)
        assert "Removed 2 item(s)" in result

    def test_remove_file_item(self):
        conv = make_conversation_with_items(
            TextItem(text="Note"),
            FileReferenceItem(path="/file.py"),
        )
        context = make_context(conv)

        result = remove_working_set_items(context, indices=[1])

        assert conv.working_set is not None
        assert len(conv.working_set) == 1
        assert isinstance(result, str)
        assert "[file]" in result
        assert "/file.py" in result

    def test_remove_directory_item(self):
        conv = make_conversation_with_items(
            DirectoryReferenceItem(
                path="/src", pattern="*.py", recursive=False, case_sensitive=True
            ),
        )
        context = make_context(conv)

        result = remove_working_set_items(context, indices=[0])

        assert conv.working_set is not None
        assert len(conv.working_set) == 0
        assert isinstance(result, str)
        assert "[directory]" in result

    def test_remove_out_of_range_index(self):
        conv = make_conversation_with_items(TextItem(text="Only item"))
        context = make_context(conv)

        result = remove_working_set_items(context, indices=[5])

        assert isinstance(result, str)
        assert "out of range" in result
        assert conv.working_set is not None
        assert len(conv.working_set) == 1

    def test_remove_empty_working_set(self):
        conv = Conversation()
        conv.working_set = WorkingSet()
        context = make_context(conv)

        result = remove_working_set_items(context, indices=[0])

        assert isinstance(result, str)
        assert "Error" in result

    def test_remove_no_working_set(self):
        conv = Conversation()
        context = make_context(conv)

        result = remove_working_set_items(context, indices=[0])

        assert isinstance(result, str)
        assert "Error" in result

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = remove_working_set_items(context, indices=[0])

        assert isinstance(result, str)
        assert "Error" in result

    def test_displayed_cache_not_updated(self):
        conv = make_conversation_with_items(
            TextItem(text="Item 1"), TextItem(text="Item 2")
        )
        assert conv.working_set is not None
        conv.working_set.update()
        initial_displayed = conv.working_set.displayed
        context = make_context(conv)

        remove_working_set_items(context, indices=[0])

        assert conv.working_set.displayed == initial_displayed


# ---------------------------------------------------------------------------
# clear_working_set
# ---------------------------------------------------------------------------


class TestClearWorkingSet:
    def test_clear_working_set(self):
        conv = make_conversation_with_items(
            TextItem(text="Item 1"),
            FileReferenceItem(path="/file.py"),
            TextItem(text="Item 2"),
        )
        context = make_context(conv)

        result = clear_working_set(context)

        assert conv.working_set is not None
        assert len(conv.working_set) == 0
        assert isinstance(result, str)
        assert "Cleared all 3 item(s)" in result

    def test_clear_already_empty(self):
        conv = Conversation()
        conv.working_set = WorkingSet()
        context = make_context(conv)

        result = clear_working_set(context)

        assert isinstance(result, str)
        assert "already empty" in result

    def test_clear_no_working_set(self):
        conv = Conversation()
        context = make_context(conv)

        result = clear_working_set(context)

        assert isinstance(result, str)
        assert "already empty" in result

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = clear_working_set(context)

        assert isinstance(result, str)
        assert "Error" in result

    def test_displayed_cache_not_updated(self):
        conv = make_conversation_with_items(TextItem(text="Item"))
        assert conv.working_set is not None
        conv.working_set.update()
        initial_displayed = conv.working_set.displayed
        context = make_context(conv)

        clear_working_set(context)

        assert conv.working_set.displayed == initial_displayed


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------


class TestWorkingSetToolWorkflows:
    def test_add_remove_add_workflow(self):
        """Add items, remove some, add more."""
        conv = Conversation()
        context = make_context(conv)

        # Add items
        add_working_set_text(context, text="Note 1")
        add_working_set_file(context, path="/file.py")
        add_working_set_directory(context, path="/src", pattern="*.py")
        assert conv.working_set is not None
        assert len(conv.working_set) == 3

        # Remove middle item
        remove_working_set_items(context, indices=[1])
        assert len(conv.working_set) == 2
        assert isinstance(conv.working_set[0], TextItem)
        assert isinstance(conv.working_set[1], DirectoryReferenceItem)

        # Add more
        add_working_set_text(context, text="Note 2")
        assert len(conv.working_set) == 3

    def test_add_clear_add_workflow(self):
        """Add items, clear all, add more."""
        conv = Conversation()
        context = make_context(conv)

        add_working_set_text(context, text="Item 1")
        add_working_set_text(context, text="Item 2")
        clear_working_set(context)
        assert conv.working_set is not None
        assert len(conv.working_set) == 0

        add_working_set_text(context, text="New item")
        assert len(conv.working_set) == 1

    def test_update_refreshes_displayed(self):
        """After update(), the displayed cache should reflect changes."""
        conv = Conversation()
        context = make_context(conv)

        add_working_set_text(context, text="Test item")

        assert conv.working_set is not None
        # Call update to refresh
        conv.working_set.update()

        assert conv.working_set.displayed is not None
        assert "Test item" in conv.working_set.displayed
        assert "<item index=0>" in conv.working_set.displayed

    def test_mixed_item_types_in_working_set(self):
        """Working set can contain mixed item types."""
        conv = Conversation()
        context = make_context(conv)

        add_working_set_text(context, text="A note")
        add_working_set_file(context, path="/file.py", start_line=0, end_line=10)
        add_working_set_directory(context, path="/src", pattern="*.py", recursive=True)

        assert conv.working_set is not None
        assert len(conv.working_set) == 3
        assert isinstance(conv.working_set[0], TextItem)
        assert isinstance(conv.working_set[1], FileReferenceItem)
        assert isinstance(conv.working_set[2], DirectoryReferenceItem)

        # Verify update renders all items
        conv.working_set.update()
        displayed = conv.working_set.displayed
        assert displayed is not None
        assert "<item index=0>" in displayed
        assert "<item index=1>" in displayed
        assert "<item index=2>" in displayed
