"""Tests for bond.conversation.working_set module."""

import pytest
from pydantic import TypeAdapter

from bond.conversation.working_set import WorkingSet
from bond.conversation.working_set_item import (
    DirectoryReferenceItem,
    FileReferenceItem,
    TextItem,
    WorkingSetItem,
)

# TypeAdapter for the WorkingSetItem union type (used for validation)
working_set_item_adapter = TypeAdapter(WorkingSetItem)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_text_item(text: str = "Hello") -> TextItem:
    return TextItem(text=text)


def make_file_item(path: str = "/tmp/test.txt") -> FileReferenceItem:
    return FileReferenceItem(path=path)


def make_dir_item(path: str = "/tmp") -> DirectoryReferenceItem:
    return DirectoryReferenceItem(
        path=path,
        pattern="*.py",
        recursive=False,
        case_sensitive=True,
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestWorkingSetCreation:
    def test_default_creation_empty(self):
        ws = WorkingSet()
        assert ws.items == []
        assert len(ws.items) == 0

    def test_creation_with_items(self):
        items: list[WorkingSetItem] = [
            make_text_item("First"),
            make_text_item("Second"),
        ]
        ws = WorkingSet(items=items)
        assert len(ws.items) == 2
        assert isinstance(ws.items[0], TextItem)
        assert ws.items[0].text == "First"
        assert isinstance(ws.items[1], TextItem)
        assert ws.items[1].text == "Second"

    def test_creation_with_mixed_item_types(self):
        items: list[WorkingSetItem] = [
            make_text_item("A text note"),
            make_file_item("/path/to/file.txt"),
            make_dir_item("/path/to/dir"),
        ]
        ws = WorkingSet(items=items)
        assert len(ws.items) == 3
        assert isinstance(ws.items[0], TextItem)
        assert isinstance(ws.items[1], FileReferenceItem)
        assert isinstance(ws.items[2], DirectoryReferenceItem)

    def test_default_factory_creates_new_list(self):
        """Each instance should get its own list, not a shared one."""
        ws1 = WorkingSet()
        ws2 = WorkingSet()
        ws1.items.append(make_text_item("Only in ws1"))
        assert len(ws1.items) == 1
        assert len(ws2.items) == 0


# ---------------------------------------------------------------------------
# Item access and mutation
# ---------------------------------------------------------------------------


class TestWorkingSetItemAccess:
    def test_append_item(self):
        ws = WorkingSet()
        ws.items.append(make_text_item("New item"))
        assert len(ws.items) == 1
        assert isinstance(ws.items[0], TextItem)
        assert ws.items[0].text == "New item"

    def test_append_multiple_items(self):
        ws = WorkingSet()
        ws.items.append(make_text_item("First"))
        ws.items.append(make_file_item("/file.txt"))
        ws.items.append(make_dir_item("/dir"))
        assert len(ws.items) == 3

    def test_items_is_mutable_list(self):
        ws = WorkingSet(items=[make_text_item("Original")])
        ws.items[0] = make_text_item("Replaced")
        assert ws.items[0].text == "Replaced"

    def test_clear_items(self):
        ws = WorkingSet(items=[make_text_item("Item 1"), make_text_item("Item 2")])
        ws.items.clear()
        assert len(ws.items) == 0

    def test_iterate_items(self):
        ws = WorkingSet(
            items=[
                make_text_item("A"),
                make_text_item("B"),
                make_text_item("C"),
            ]
        )
        texts = [item.text for item in ws.items if isinstance(item, TextItem)]
        assert texts == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Serialization - model_dump
# ---------------------------------------------------------------------------


class TestWorkingSetSerialization:
    def test_model_dump_empty(self):
        ws = WorkingSet()
        data = ws.model_dump()
        assert data == {"items": [], "displayed": None}

    def test_model_dump_with_text_items(self):
        ws = WorkingSet(items=[make_text_item("Hello")])
        data = ws.model_dump()
        assert "items" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["type"] == "text"
        assert data["items"][0]["text"] == "Hello"

    def test_model_dump_with_mixed_items(self):
        ws = WorkingSet(
            items=[
                make_text_item("Note"),
                make_file_item("/file.txt"),
                make_dir_item("/dir"),
            ]
        )
        data = ws.model_dump()
        assert len(data["items"]) == 3
        # Each item should have its type discriminator
        assert data["items"][0]["type"] == "text"
        assert data["items"][1]["type"] == "file"
        assert data["items"][2]["type"] == "directory"

    def test_model_dump_json_mode(self):
        ws = WorkingSet(items=[make_text_item("JSON test")])
        data = ws.model_dump(mode="json")
        assert data["items"][0]["type"] == "text"
        assert data["items"][0]["text"] == "JSON test"


# ---------------------------------------------------------------------------
# Deserialization - model_validate (roundtrip)
# ---------------------------------------------------------------------------


class TestWorkingSetDeserialization:
    def test_roundtrip_empty(self):
        ws = WorkingSet()
        data = ws.model_dump(mode="json")
        ws2 = WorkingSet.model_validate(data)
        assert ws2.items == []

    def test_roundtrip_with_text_items(self):
        ws = WorkingSet(
            items=[
                make_text_item("First"),
                make_text_item("Second"),
            ]
        )
        data = ws.model_dump(mode="json")
        ws2 = WorkingSet.model_validate(data)
        assert len(ws2.items) == 2
        assert isinstance(ws2.items[0], TextItem)
        assert ws2.items[0].text == "First"
        assert isinstance(ws2.items[1], TextItem)
        assert ws2.items[1].text == "Second"

    def test_roundtrip_with_mixed_items(self):
        """Polymorphic deserialization: each item type should be correctly restored."""
        ws = WorkingSet(
            items=[
                make_text_item("A note"),
                make_file_item("/path/to/file.txt"),
                make_dir_item("/path/to/dir"),
            ]
        )
        data = ws.model_dump(mode="json")
        ws2 = WorkingSet.model_validate(data)
        assert len(ws2.items) == 3
        assert isinstance(ws2.items[0], TextItem)
        assert ws2.items[0].text == "A note"
        assert isinstance(ws2.items[1], FileReferenceItem)
        assert ws2.items[1].path == "/path/to/file.txt"
        assert isinstance(ws2.items[2], DirectoryReferenceItem)
        assert ws2.items[2].path == "/path/to/dir"
        assert ws2.items[2].pattern == "*.py"

    def test_roundtrip_preserves_file_item_line_ranges(self):
        item = FileReferenceItem(path="/file.txt", start_line=5, end_line=10)
        ws = WorkingSet(items=[item])
        data = ws.model_dump(mode="json")
        ws2 = WorkingSet.model_validate(data)
        assert isinstance(ws2.items[0], FileReferenceItem)
        assert ws2.items[0].start_line == 5
        assert ws2.items[0].end_line == 10

    def test_roundtrip_preserves_directory_item_options(self):
        item = DirectoryReferenceItem(
            path="/dir",
            pattern="*.txt",
            recursive=True,
            case_sensitive=False,
        )
        ws = WorkingSet(items=[item])
        data = ws.model_dump(mode="json")
        ws2 = WorkingSet.model_validate(data)
        assert isinstance(ws2.items[0], DirectoryReferenceItem)
        assert ws2.items[0].pattern == "*.txt"
        assert ws2.items[0].recursive is True
        assert ws2.items[0].case_sensitive is False


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


class TestWorkingSetJsonSerialization:
    def test_model_dump_json_empty(self):
        ws = WorkingSet()
        json_str = ws.model_dump_json()
        assert '"items":[]' in json_str

    def test_model_dump_json_with_items(self):
        ws = WorkingSet(items=[make_text_item("JSON")])
        json_str = ws.model_dump_json()
        assert '"type":"text"' in json_str
        assert '"text":"JSON"' in json_str

    def test_model_validate_json_roundtrip(self):
        ws = WorkingSet(
            items=[
                make_text_item("Text item"),
                make_file_item("/file.txt"),
            ]
        )
        json_str = ws.model_dump_json()
        ws2 = WorkingSet.model_validate_json(json_str)
        assert len(ws2.items) == 2
        assert isinstance(ws2.items[0], TextItem)
        assert isinstance(ws2.items[1], FileReferenceItem)


# ---------------------------------------------------------------------------
# Validation from dict
# ---------------------------------------------------------------------------


class TestWorkingSetValidation:
    def test_validate_from_dict_empty(self):
        ws = WorkingSet.model_validate({"items": []})
        assert ws.items == []

    def test_validate_from_dict_with_items(self):
        data = {
            "items": [
                {"type": "text", "text": "Hello"},
                {
                    "type": "file",
                    "path": "/file.txt",
                    "start_line": None,
                    "end_line": None,
                },
            ]
        }
        ws = WorkingSet.model_validate(data)
        assert len(ws.items) == 2
        assert isinstance(ws.items[0], TextItem)
        assert isinstance(ws.items[1], FileReferenceItem)

    def test_validate_from_dict_missing_items_defaults_to_empty(self):
        ws = WorkingSet.model_validate({})
        assert ws.items == []

    def test_validate_with_invalid_item_type_raises(self):
        data = {
            "items": [
                {"type": "invalid_type", "text": "Hello"},
            ]
        }
        with pytest.raises(Exception):  # ValidationError
            WorkingSet.model_validate(data)
