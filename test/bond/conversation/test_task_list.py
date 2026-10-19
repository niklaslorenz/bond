"""Tests for bond.conversation.task_list module."""

import pytest
from pydantic import ValidationError

from bond.conversation.task_list import TaskList, TaskListItem


# ---------------------------------------------------------------------------
# TaskListItem
# ---------------------------------------------------------------------------


class TestTaskListItem:
    def test_creation(self):
        item = TaskListItem(index=0, description="Do something", is_complete=False)
        assert item.index == 0
        assert item.description == "Do something"
        assert item.is_complete is False

    def test_render_incomplete(self):
        item = TaskListItem(index=0, description="Do something", is_complete=False)
        assert item.render() == "0. [ ] Do something"

    def test_render_complete(self):
        item = TaskListItem(index=1, description="Do something", is_complete=True)
        assert item.render() == "1. [x] Do something"

    def test_render_multi_digit_index(self):
        item = TaskListItem(index=10, description="Task ten", is_complete=False)
        assert item.render() == "10. [ ] Task ten"

    def test_serialization(self):
        item = TaskListItem(index=0, description="Test", is_complete=True)
        data = item.model_dump()
        assert data == {"index": 0, "description": "Test", "is_complete": True}

    def test_deserialization(self):
        data = {"index": 2, "description": "Test task", "is_complete": False}
        item = TaskListItem.model_validate(data)
        assert item.index == 2
        assert item.description == "Test task"
        assert item.is_complete is False


# ---------------------------------------------------------------------------
# TaskList - Creation & Basic Properties
# ---------------------------------------------------------------------------


class TestTaskListCreation:
    def test_default_creation_empty(self):
        tl = TaskList()
        assert tl.content == []
        assert len(tl) == 0

    def test_creation_with_items(self):
        items = [
            TaskListItem(index=0, description="First", is_complete=False),
            TaskListItem(index=1, description="Second", is_complete=True),
        ]
        tl = TaskList(content=items)
        assert len(tl) == 2
        assert tl.content[0].description == "First"
        assert tl.content[1].is_complete is True


# ---------------------------------------------------------------------------
# TaskList - Sequence Protocol (__len__, __getitem__, __iter__)
# ---------------------------------------------------------------------------


class TestTaskListSequenceProtocol:
    def test_len_empty(self):
        tl = TaskList()
        assert len(tl) == 0

    def test_len_with_items(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.add_item("Task 3")
        assert len(tl) == 3

    def test_getitem_int(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        item = tl[0]
        assert item.description == "First"
        assert item.index == 0

    def test_getitem_second_item(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        item = tl[1]
        assert item.description == "Second"
        assert item.index == 1

    def test_getitem_negative_index(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        tl.add_item("Third")
        item = tl[-1]
        assert item.description == "Third"
        assert item.index == 2

    def test_getitem_slice(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        tl.add_item("Third")
        items = tl[0:2]
        assert len(items) == 2
        assert items[0].description == "First"
        assert items[1].description == "Second"

    def test_getitem_slice_all(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        items = tl[:]
        assert len(items) == 2

    def test_getitem_out_of_bounds_raises(self):
        tl = TaskList()
        tl.add_item("Only item")
        with pytest.raises(IndexError):
            _ = tl[5]

    def test_iter_empty(self):
        tl = TaskList()
        items = list(tl)
        assert items == []

    def test_iter_with_items(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        descriptions = [item.description for item in tl]
        assert descriptions == ["First", "Second"]

    def test_iter_preserves_order(self):
        tl = TaskList()
        tl.add_item("A")
        tl.add_item("B")
        tl.add_item("C")
        descriptions = [item.description for item in tl]
        assert descriptions == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# TaskList - add_item
# ---------------------------------------------------------------------------


class TestTaskListAddItem:
    def test_add_item_returns_created_item(self):
        tl = TaskList()
        item = tl.add_item("My task")
        assert isinstance(item, TaskListItem)
        assert item.description == "My task"
        assert item.is_complete is False

    def test_add_item_assigns_index_zero_to_first(self):
        tl = TaskList()
        item = tl.add_item("First")
        assert item.index == 0

    def test_add_item_assigns_sequential_indices(self):
        tl = TaskList()
        item0 = tl.add_item("First")
        item1 = tl.add_item("Second")
        item2 = tl.add_item("Third")
        assert item0.index == 0
        assert item1.index == 1
        assert item2.index == 2

    def test_add_item_increases_length(self):
        tl = TaskList()
        assert len(tl) == 0
        tl.add_item("One")
        assert len(tl) == 1
        tl.add_item("Two")
        assert len(tl) == 2

    def test_add_item_appends_to_content(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        assert tl.content[0].description == "First"
        assert tl.content[1].description == "Second"

    def test_add_item_is_incomplete_by_default(self):
        tl = TaskList()
        item = tl.add_item("Task")
        assert item.is_complete is False


# ---------------------------------------------------------------------------
# TaskList - remove_item
# ---------------------------------------------------------------------------


class TestTaskListRemoveItem:
    def test_remove_item_returns_removed_item(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        removed = tl.remove_item(0)
        assert removed.description == "First"

    def test_remove_item_decreases_length(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        tl.remove_item(0)
        assert len(tl) == 1

    def test_remove_item_removes_correct_item(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        tl.add_item("Third")
        tl.remove_item(1)
        assert len(tl) == 2
        assert tl[0].description == "First"
        assert tl[1].description == "Third"

    def test_remove_item_recomputes_indices(self):
        """After removal, remaining items should have sequential indices."""
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        tl.add_item("Third")
        tl.remove_item(0)
        # Remaining items should be re-indexed
        assert tl[0].index == 0
        assert tl[0].description == "Second"
        assert tl[1].index == 1
        assert tl[1].description == "Third"

    def test_remove_item_from_middle_recomputes_indices(self):
        tl = TaskList()
        tl.add_item("A")
        tl.add_item("B")
        tl.add_item("C")
        tl.add_item("D")
        tl.remove_item(1)  # Remove "B"
        assert tl[0].index == 0
        assert tl[0].description == "A"
        assert tl[1].index == 1
        assert tl[1].description == "C"
        assert tl[2].index == 2
        assert tl[2].description == "D"

    def test_remove_last_item(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        removed = tl.remove_item(1)
        assert removed.description == "Second"
        assert len(tl) == 1
        assert tl[0].description == "First"

    def test_remove_only_item(self):
        tl = TaskList()
        tl.add_item("Only")
        tl.remove_item(0)
        assert len(tl) == 0

    def test_remove_out_of_bounds_raises(self):
        tl = TaskList()
        tl.add_item("Only")
        with pytest.raises(IndexError):
            tl.remove_item(5)


# ---------------------------------------------------------------------------
# TaskList - complete_item
# ---------------------------------------------------------------------------


class TestTaskListCompleteItem:
    def test_complete_item_returns_completed_item(self):
        tl = TaskList()
        tl.add_item("My task")
        item = tl.complete_item(0)
        assert item.is_complete is True

    def test_complete_item_marks_as_complete(self):
        tl = TaskList()
        tl.add_item("Task")
        assert tl[0].is_complete is False
        tl.complete_item(0)
        assert tl[0].is_complete is True

    def test_complete_item_preserves_description(self):
        tl = TaskList()
        tl.add_item("Important task")
        item = tl.complete_item(0)
        assert item.description == "Important task"

    def test_complete_item_preserves_index(self):
        tl = TaskList()
        tl.add_item("First")
        tl.add_item("Second")
        item = tl.complete_item(1)
        assert item.index == 1

    def test_complete_multiple_items(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.add_item("Task 3")
        tl.complete_item(0)
        tl.complete_item(2)
        assert tl[0].is_complete is True
        assert tl[1].is_complete is False
        assert tl[2].is_complete is True

    def test_complete_out_of_bounds_raises(self):
        tl = TaskList()
        tl.add_item("Only")
        with pytest.raises(IndexError):
            tl.complete_item(5)


# ---------------------------------------------------------------------------
# TaskList - clear_complete_items
# ---------------------------------------------------------------------------


class TestTaskListClearCompleteItems:
    def test_clear_complete_items_removes_completed(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.add_item("Task 3")
        tl.complete_item(0)
        tl.complete_item(2)
        tl.clear_complete_items()
        assert len(tl) == 1
        assert tl[0].description == "Task 2"

    def test_clear_complete_items_keeps_incomplete(self):
        tl = TaskList()
        tl.add_item("Incomplete 1")
        tl.add_item("Incomplete 2")
        tl.clear_complete_items()
        assert len(tl) == 2

    def test_clear_complete_items_recomputes_indices(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.add_item("Task 3")
        tl.complete_item(0)
        tl.clear_complete_items()
        # Remaining items should be re-indexed
        assert tl[0].index == 0
        assert tl[0].description == "Task 2"
        assert tl[1].index == 1
        assert tl[1].description == "Task 3"

    def test_clear_complete_items_on_empty_list(self):
        tl = TaskList()
        tl.clear_complete_items()
        assert len(tl) == 0

    def test_clear_complete_items_when_none_complete(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.clear_complete_items()
        assert len(tl) == 2

    def test_clear_complete_items_when_all_complete(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.complete_item(0)
        tl.complete_item(1)
        tl.clear_complete_items()
        assert len(tl) == 0


# ---------------------------------------------------------------------------
# TaskList - render
# ---------------------------------------------------------------------------


class TestTaskListRender:
    def test_render_empty_list(self):
        tl = TaskList()
        assert tl.render() == ""

    def test_render_single_item(self):
        tl = TaskList()
        tl.add_item("Do something")
        assert tl.render() == "0. [ ] Do something"

    def test_render_multiple_items(self):
        tl = TaskList()
        tl.add_item("First task")
        tl.add_item("Second task")
        result = tl.render()
        lines = result.split("\n")
        assert len(lines) == 2
        assert lines[0] == "0. [ ] First task"
        assert lines[1] == "1. [ ] Second task"

    def test_render_with_completed_items(self):
        tl = TaskList()
        tl.add_item("Done task")
        tl.add_item("Pending task")
        tl.complete_item(0)
        result = tl.render()
        lines = result.split("\n")
        assert lines[0] == "0. [x] Done task"
        assert lines[1] == "1. [ ] Pending task"

    def test_render_after_clear_complete_items(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.add_item("Task 3")
        tl.complete_item(0)
        tl.clear_complete_items()
        result = tl.render()
        lines = result.split("\n")
        assert len(lines) == 2
        assert lines[0] == "0. [ ] Task 2"
        assert lines[1] == "1. [ ] Task 3"


# ---------------------------------------------------------------------------
# TaskList - Serialization
# ---------------------------------------------------------------------------


class TestTaskListSerialization:
    def test_serialization_roundtrip(self):
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.complete_item(0)
        data = tl.model_dump(mode="json")
        tl2 = TaskList.model_validate(data)
        assert len(tl2) == 2
        assert tl2[0].description == "Task 1"
        assert tl2[0].is_complete is True
        assert tl2[1].description == "Task 2"
        assert tl2[1].is_complete is False

    def test_serialization_preserves_indices(self):
        tl = TaskList()
        tl.add_item("A")
        tl.add_item("B")
        tl.add_item("C")
        data = tl.model_dump(mode="json")
        tl2 = TaskList.model_validate(data)
        assert tl2[0].index == 0
        assert tl2[1].index == 1
        assert tl2[2].index == 2


# ---------------------------------------------------------------------------
# TaskList - Combined workflows
# ---------------------------------------------------------------------------


class TestTaskListWorkflows:
    def test_add_complete_remove_workflow(self):
        """Simulate a typical workflow: add tasks, complete some, remove one."""
        tl = TaskList()
        tl.add_item("Write tests")
        tl.add_item("Fix bugs")
        tl.add_item("Deploy")

        tl.complete_item(0)  # Complete "Write tests"
        tl.remove_item(1)  # Remove "Fix bugs"

        assert len(tl) == 2
        assert tl[0].description == "Write tests"
        assert tl[0].is_complete is True
        assert tl[1].description == "Deploy"
        assert tl[1].is_complete is False
        assert tl[1].index == 1  # Re-indexed

    def test_add_clear_add_workflow(self):
        """Add tasks, clear completed, then add more."""
        tl = TaskList()
        tl.add_item("Task 1")
        tl.add_item("Task 2")
        tl.complete_item(0)
        tl.clear_complete_items()

        # Add new task - should get index 1 (after the remaining item)
        new_item = tl.add_item("Task 3")
        assert new_item.index == 1
        assert len(tl) == 2
        assert tl[0].description == "Task 2"
        assert tl[1].description == "Task 3"
