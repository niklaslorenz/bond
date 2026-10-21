"""Tests for bond.tools.task_list module."""

from bond.conversation.conversation import Conversation
from bond.conversation.task_list import TaskList
from bond.tools.task_list import (
    add_tasks,
    clear_completed_tasks,
    clear_tasks,
    complete_tasks,
    delete_tasks,
)
from bond.tools.tool import ToolCallContext

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


def make_conversation_with_tasks(*descriptions: str) -> Conversation:
    """Create a conversation with a task list containing the given tasks."""
    conv = Conversation()
    conv.task_list = TaskList()
    for desc in descriptions:
        conv.task_list.add_item(desc)
    return conv


# ---------------------------------------------------------------------------
# add_tasks
# ---------------------------------------------------------------------------


class TestAddTasks:
    def test_add_single_task(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_tasks(context, tasks=["Write tests"])

        assert conv.task_list is not None
        assert len(conv.task_list) == 1
        assert conv.task_list[0].description == "Write tests"
        assert conv.task_list[0].is_complete is False
        assert isinstance(result, str)
        assert "Added 1 task(s)" in result
        assert "Write tests" in result

    def test_add_multiple_tasks(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_tasks(context, tasks=["Task 1", "Task 2", "Task 3"])

        assert conv.task_list is not None
        assert len(conv.task_list) == 3
        assert conv.task_list[0].description == "Task 1"
        assert conv.task_list[1].description == "Task 2"
        assert conv.task_list[2].description == "Task 3"
        assert isinstance(result, str)
        assert "Added 3 task(s)" in result

    def test_add_to_existing_task_list(self):
        conv = make_conversation_with_tasks("Existing task")
        context = make_context(conv)

        add_tasks(context, tasks=["New task"])

        assert conv.task_list is not None
        assert len(conv.task_list) == 2
        assert conv.task_list[0].description == "Existing task"
        assert conv.task_list[1].description == "New task"
        assert conv.task_list[1].index == 1

    def test_add_initializes_task_list_if_none(self):
        conv = Conversation()
        assert conv.task_list is None
        context = make_context(conv)

        add_tasks(context, tasks=["First task"])

        assert conv.task_list is not None
        assert len(conv.task_list) == 1

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = add_tasks(context, tasks=["Task"])

        assert isinstance(result, str)
        assert "Error" in result
        assert "No conversation context" in result

    def test_result_mentions_summarization(self):
        conv = Conversation()
        context = make_context(conv)

        result = add_tasks(context, tasks=["Task"])

        assert isinstance(result, str)
        assert "summarization" in result.lower()

    def test_displayed_cache_not_updated(self):
        """The displayed cache should not be updated by tool calls."""
        conv = Conversation()
        conv.task_list = TaskList()
        conv.task_list.update()  # Initial update
        initial_displayed = conv.task_list.displayed
        context = make_context(conv)

        add_tasks(context, tasks=["New task"])

        # Displayed should still be the old value
        assert conv.task_list.displayed == initial_displayed


# ---------------------------------------------------------------------------
# complete_tasks
# ---------------------------------------------------------------------------


class TestCompleteTasks:
    def test_complete_single_task(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2")
        context = make_context(conv)

        result = complete_tasks(context, indices=[0])

        assert conv.task_list is not None
        assert conv.task_list[0].is_complete is True
        assert conv.task_list[1].is_complete is False
        assert isinstance(result, str)
        assert "Marked 1 task(s)" in result

    def test_complete_multiple_tasks(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2", "Task 3")
        context = make_context(conv)

        result = complete_tasks(context, indices=[0, 2])

        assert conv.task_list is not None
        assert conv.task_list[0].is_complete is True
        assert conv.task_list[1].is_complete is False
        assert conv.task_list[2].is_complete is True
        assert isinstance(result, str)
        assert "Marked 2 task(s)" in result

    def test_complete_out_of_range_index(self):
        conv = make_conversation_with_tasks("Task 1")
        context = make_context(conv)

        result = complete_tasks(context, indices=[5])

        assert isinstance(result, str)
        assert "Error" in result and "out of range" in result
        assert conv.task_list is not None
        assert conv.task_list[0].is_complete is False

    def test_complete_negative_index(self):
        conv = make_conversation_with_tasks("Task 1")
        context = make_context(conv)

        result = complete_tasks(context, indices=[-1])

        assert isinstance(result, str)
        assert "out of range" in result

    def test_complete_empty_task_list(self):
        conv = Conversation()
        conv.task_list = TaskList()
        context = make_context(conv)

        result = complete_tasks(context, indices=[0])

        assert isinstance(result, str)
        assert "Error" in result
        assert "empty" in result.lower()

    def test_complete_no_task_list(self):
        conv = Conversation()
        context = make_context(conv)

        result = complete_tasks(context, indices=[0])

        assert isinstance(result, str)
        assert "Error" in result

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = complete_tasks(context, indices=[0])

        assert isinstance(result, str)
        assert "Error" in result

    def test_mixed_valid_and_invalid_indices(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2")
        context = make_context(conv)

        result = complete_tasks(context, indices=[0, 5])

        assert conv.task_list is not None
        assert conv.task_list[0].is_complete is True
        assert isinstance(result, str)
        assert "Error" in result and "out of range" in result

    def test_displayed_cache_not_updated(self):
        conv = make_conversation_with_tasks("Task 1")
        assert conv.task_list is not None
        conv.task_list.update()
        initial_displayed = conv.task_list.displayed
        context = make_context(conv)

        complete_tasks(context, indices=[0])

        assert conv.task_list.displayed == initial_displayed


# ---------------------------------------------------------------------------
# delete_tasks
# ---------------------------------------------------------------------------


class TestDeleteTasks:
    def test_delete_single_task(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2", "Task 3")
        context = make_context(conv)

        result = delete_tasks(context, indices=[1])

        assert conv.task_list is not None
        assert len(conv.task_list) == 2
        assert conv.task_list[0].description == "Task 1"
        assert conv.task_list[1].description == "Task 3"
        assert isinstance(result, str)
        assert "Deleted 1 task(s)" in result

    def test_delete_multiple_tasks(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2", "Task 3", "Task 4")
        context = make_context(conv)

        result = delete_tasks(context, indices=[0, 2])

        assert conv.task_list is not None
        assert len(conv.task_list) == 2
        assert conv.task_list[0].description == "Task 2"
        assert conv.task_list[1].description == "Task 4"
        assert isinstance(result, str)
        assert "Deleted 2 task(s)" in result

    def test_delete_recomputes_indices(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2", "Task 3")
        context = make_context(conv)

        delete_tasks(context, indices=[0])

        assert conv.task_list is not None
        assert conv.task_list[0].index == 0
        assert conv.task_list[0].description == "Task 2"
        assert conv.task_list[1].index == 1
        assert conv.task_list[1].description == "Task 3"

    def test_delete_out_of_range_index(self):
        conv = make_conversation_with_tasks("Task 1")
        context = make_context(conv)

        result = delete_tasks(context, indices=[5])

        assert isinstance(result, str)
        assert "out of range" in result
        assert conv.task_list is not None
        assert len(conv.task_list) == 1

    def test_delete_empty_task_list(self):
        conv = Conversation()
        conv.task_list = TaskList()
        context = make_context(conv)

        result = delete_tasks(context, indices=[0])
        assert isinstance(result, str)
        assert "Error" in result

    def test_delete_all_tasks(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2")
        context = make_context(conv)

        delete_tasks(context, indices=[0, 1])

        assert conv.task_list is not None
        assert len(conv.task_list) == 0

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = delete_tasks(context, indices=[0])

        assert isinstance(result, str)
        assert "Error" in result

    def test_displayed_cache_not_updated(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2")
        assert conv.task_list is not None
        conv.task_list.update()
        initial_displayed = conv.task_list.displayed
        context = make_context(conv)

        delete_tasks(context, indices=[0])

        assert conv.task_list.displayed == initial_displayed


# ---------------------------------------------------------------------------
# clear_tasks
# ---------------------------------------------------------------------------


class TestClearTasks:
    def test_clear_tasks(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2", "Task 3")
        context = make_context(conv)

        result = clear_tasks(context)

        assert conv.task_list is not None
        assert len(conv.task_list) == 0
        assert isinstance(result, str)
        assert "Cleared all 3 task(s)" in result

    def test_clear_already_empty(self):
        conv = Conversation()
        conv.task_list = TaskList()
        context = make_context(conv)

        result = clear_tasks(context)

        assert isinstance(result, str)
        assert "already empty" in result

    def test_clear_no_task_list(self):
        conv = Conversation()
        context = make_context(conv)

        result = clear_tasks(context)

        assert isinstance(result, str)
        assert "already empty" in result

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = clear_tasks(context)

        assert isinstance(result, str)
        assert "Error" in result

    def test_displayed_cache_not_updated(self):
        conv = make_conversation_with_tasks("Task 1")
        assert conv.task_list is not None
        conv.task_list.update()
        initial_displayed = conv.task_list.displayed
        context = make_context(conv)

        clear_tasks(context)

        assert conv.task_list.displayed == initial_displayed


# ---------------------------------------------------------------------------
# clear_completed_tasks
# ---------------------------------------------------------------------------


class TestClearCompletedTasks:
    def test_clear_completed_removes_only_completed(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2", "Task 3")
        assert conv.task_list is not None
        conv.task_list.complete_item(0)
        conv.task_list.complete_item(2)
        context = make_context(conv)

        result = clear_completed_tasks(context)

        assert len(conv.task_list) == 1
        assert conv.task_list[0].description == "Task 2"
        assert isinstance(result, str)
        assert "Removed 2 completed task(s)" in result

    def test_clear_completed_recomputes_indices(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2", "Task 3")
        assert conv.task_list is not None
        conv.task_list.complete_item(0)
        context = make_context(conv)

        clear_completed_tasks(context)

        assert conv.task_list[0].index == 0
        assert conv.task_list[0].description == "Task 2"
        assert conv.task_list[1].index == 1
        assert conv.task_list[1].description == "Task 3"

    def test_clear_completed_none_completed(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2")
        context = make_context(conv)

        result = clear_completed_tasks(context)

        assert isinstance(result, str)
        assert "No completed tasks" in result
        assert conv.task_list is not None
        assert len(conv.task_list) == 2

    def test_clear_completed_all_completed(self):
        conv = make_conversation_with_tasks("Task 1", "Task 2")
        assert conv.task_list is not None
        conv.task_list.complete_item(0)
        conv.task_list.complete_item(1)
        context = make_context(conv)

        result = clear_completed_tasks(context)

        assert len(conv.task_list) == 0
        assert isinstance(result, str)
        assert "Removed 2 completed task(s)" in result

    def test_clear_completed_empty_list(self):
        conv = Conversation()
        conv.task_list = TaskList()
        context = make_context(conv)

        result = clear_completed_tasks(context)

        assert isinstance(result, str)
        assert "empty" in result.lower()

    def test_no_conversation_returns_error(self):
        context = make_context(None)

        result = clear_completed_tasks(context)

        assert isinstance(result, str)
        assert "Error" in result

    def test_displayed_cache_not_updated(self):
        conv = make_conversation_with_tasks("Task 1")
        assert conv.task_list is not None
        conv.task_list.complete_item(0)
        conv.task_list.update()
        initial_displayed = conv.task_list.displayed
        context = make_context(conv)

        clear_completed_tasks(context)

        assert conv.task_list.displayed == initial_displayed


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------


class TestTaskListToolWorkflows:
    def test_add_complete_clear_workflow(self):
        """Simulate a typical workflow: add, complete, clear completed."""
        conv = Conversation()
        context = make_context(conv)

        # Add tasks
        add_tasks(context, tasks=["Write code", "Write tests", "Deploy"])
        assert conv.task_list is not None
        assert len(conv.task_list) == 3

        # Complete some
        complete_tasks(context, indices=[0, 1])
        assert conv.task_list[0].is_complete is True
        assert conv.task_list[1].is_complete is True
        assert conv.task_list[2].is_complete is False

        # Clear completed
        clear_completed_tasks(context)
        assert len(conv.task_list) == 1
        assert conv.task_list[0].description == "Deploy"

    def test_add_delete_add_workflow(self):
        """Add tasks, delete some, add more."""
        conv = Conversation()
        context = make_context(conv)

        add_tasks(context, tasks=["Task 1", "Task 2", "Task 3"])
        delete_tasks(context, indices=[1])
        assert conv.task_list is not None
        assert len(conv.task_list) == 2

        add_tasks(context, tasks=["Task 4"])
        assert len(conv.task_list) == 3
        assert conv.task_list[2].description == "Task 4"
        assert conv.task_list[2].index == 2

    def test_update_refreshes_displayed(self):
        """After update(), the displayed cache should reflect changes."""
        conv = Conversation()
        context = make_context(conv)

        add_tasks(context, tasks=["Task 1"])
        assert conv.task_list is not None
        # Displayed should be None or stale
        old_displayed = conv.task_list.displayed

        # Call update to refresh
        conv.task_list.update()

        assert conv.task_list.displayed is not None
        assert "Task 1" in conv.task_list.displayed
