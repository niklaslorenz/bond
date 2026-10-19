"""Tests for bond.conversation.working_set_item module."""

import pytest
from pydantic import TypeAdapter, ValidationError

from bond.conversation.working_set_item import (
    MAX_DIR_ENTRIES,
    DirectoryReferenceItem,
    FileReferenceItem,
    TextItem,
    WorkingSetItem,
    WorkingSetItemBase,
)

# TypeAdapter for the WorkingSetItem union type
working_set_item_adapter = TypeAdapter(WorkingSetItem)

# ---------------------------------------------------------------------------
# TextItem
# ---------------------------------------------------------------------------


class TestTextItem:
    def test_creation(self):
        item = TextItem(text="Hello world")
        assert item.text == "Hello world"

    def test_default_type(self):
        item = TextItem(text="Hello")
        assert item.type == "text"

    def test_render_returns_text(self):
        item = TextItem(text="Some text content")
        assert item.render() == "Some text content"

    def test_render_empty_text(self):
        item = TextItem(text="")
        assert item.render() == ""

    def test_render_multiline_text(self):
        item = TextItem(text="Line 1\nLine 2\nLine 3")
        assert item.render() == "Line 1\nLine 2\nLine 3"

    def test_is_working_set_item_base(self):
        item = TextItem(text="Test")
        assert isinstance(item, WorkingSetItemBase)

    def test_serialization(self):
        item = TextItem(text="Serialize me")
        data = item.model_dump()
        assert data == {"type": "text", "text": "Serialize me"}

    def test_deserialization(self):
        data = {"type": "text", "text": "Deserialize me"}
        item = TextItem.model_validate(data)
        assert item.text == "Deserialize me"


# ---------------------------------------------------------------------------
# FileReferenceItem - Creation & Validation
# ---------------------------------------------------------------------------


class TestFileReferenceItemCreation:
    def test_creation_with_path_only(self):
        item = FileReferenceItem(path="/some/file.txt", start_line=None, end_line=None)
        assert item.path == "/some/file.txt"
        assert item.start_line is None
        assert item.end_line is None

    def test_creation_with_all_fields(self):
        item = FileReferenceItem(
            path="/some/file.txt",
            start_line=5,
            end_line=10,
        )
        assert item.path == "/some/file.txt"
        assert item.start_line == 5
        assert item.end_line == 10

    def test_default_type(self):
        item = FileReferenceItem(path="/file.txt")
        assert item.type == "file"

    def test_start_line_zero_allowed(self):
        item = FileReferenceItem(path="/file.txt", start_line=0)
        assert item.start_line == 0

    def test_end_line_zero_allowed(self):
        item = FileReferenceItem(path="/file.txt", end_line=0)
        assert item.end_line == 0

    def test_negative_start_line_raises(self):
        with pytest.raises(ValidationError, match="start_line"):
            FileReferenceItem(path="/file.txt", start_line=-1)

    def test_negative_end_line_raises(self):
        with pytest.raises(ValidationError, match="end_line"):
            FileReferenceItem(path="/file.txt", end_line=-5)

    def test_both_negative_lines_raises(self):
        with pytest.raises(ValidationError):
            FileReferenceItem(path="/file.txt", start_line=-1, end_line=-2)

    def test_is_working_set_item_base(self):
        item = FileReferenceItem(path="/file.txt")
        assert isinstance(item, WorkingSetItemBase)


# ---------------------------------------------------------------------------
# FileReferenceItem - render() with file system
# ---------------------------------------------------------------------------


class TestFileReferenceItemRender:
    def test_render_nonexistent_file(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist.txt"
        item = FileReferenceItem(path=str(nonexistent))
        result = item.render()
        assert "does not exist" in result
        assert nonexistent.as_posix() in result

    def test_render_path_is_directory(self, tmp_path):
        """If path points to a directory, should report it's not a file."""
        item = FileReferenceItem(path=str(tmp_path))
        result = item.render()
        assert "is not a file" in result
        assert tmp_path.as_posix() in result

    def test_render_existing_file_full_content(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello\nWorld\nFoo", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path))
        result = item.render()
        assert "Contents of" in result
        assert file_path.as_posix() in result
        assert "Hello" in result
        assert "World" in result
        assert "Foo" in result

    def test_render_file_header_shows_line_range(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Line 1\nLine 2\nLine 3", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path))
        result = item.render()
        # Default: start_line is None -> treated as 0, so shows "lines 1 to <eof>"
        assert "lines 1 to <eof>" in result

    def test_render_file_with_start_line(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Line 1\nLine 2\nLine 3\nLine 4", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path), start_line=1)
        result = item.render()
        # start_line=1 means start from index 1 (second line)
        # Header shows (1 + 1) = 2
        assert "lines 2 to <eof>" in result
        assert "Line 2" in result
        assert "Line 3" in result
        assert "Line 4" in result
        assert "Line 1" not in result.split(":")[-1]  # Not in content part

    def test_render_file_with_end_line(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Line 1\nLine 2\nLine 3\nLine 4", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path), end_line=2)
        result = item.render()
        # end_line=2 means up to index 2 (exclusive), so lines 0 and 1
        assert "lines 1 to 2" in result
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" not in result.split(":")[-1]
        assert "Line 4" not in result.split(":")[-1]

    def test_render_file_with_start_and_end_line(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path), start_line=1, end_line=3)
        result = item.render()
        # start_line=1 -> header shows "lines 2", end_line=3 -> header shows "to 3"
        assert "lines 2 to 3" in result
        content_part = result.split(":\n")[-1]
        assert "Line 2" in content_part
        assert "Line 3" in content_part
        assert "Line 1" not in content_part
        assert "Line 4" not in content_part

    def test_render_file_start_line_zero(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("First\nSecond", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path), start_line=0)
        result = item.render()
        # start_line=0 -> header shows "lines 1"
        assert "lines 1 to <eof>" in result
        assert "First" in result
        assert "Second" in result

    def test_render_file_end_line_beyond_file_length(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Only line", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path), end_line=100)
        result = item.render()
        # Should not crash, just show what's available
        assert "Only line" in result

    def test_render_empty_file(self, tmp_path):
        file_path = tmp_path / "empty.txt"
        file_path.write_text("", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path))
        result = item.render()
        assert "Contents of" in result
        assert file_path.as_posix() in result

    def test_render_file_with_unicode_content(self, tmp_path):
        file_path = tmp_path / "unicode.txt"
        file_path.write_text("Hello 世界 🌍\nПривет", encoding="utf-8")
        item = FileReferenceItem(path=str(file_path))
        result = item.render()
        assert "世界" in result
        assert "🌍" in result
        assert "Привет" in result

    def test_render_expands_user_path(self, tmp_path, monkeypatch):
        """~ in path should be expanded."""
        # Create a file in a temp "home" directory
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        test_file = fake_home / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        monkeypatch.setenv("HOME", str(fake_home))
        item = FileReferenceItem(path="~/test.txt")
        result = item.render()
        assert "content" in result

    def test_render_absolute_path(self, tmp_path):
        file_path = tmp_path / "absolute.txt"
        file_path.write_text("absolute content", encoding="utf-8")
        # Pass absolute path directly
        item = FileReferenceItem(path=file_path.as_posix())
        result = item.render()
        assert "absolute content" in result


# ---------------------------------------------------------------------------
# DirectoryReferenceItem - Creation
# ---------------------------------------------------------------------------


class TestDirectoryReferenceItemCreation:
    def test_creation_with_all_fields(self):
        item = DirectoryReferenceItem(
            path="/some/dir",
            pattern="*.py",
            recursive=True,
            case_sensitive=False,
        )
        assert item.path == "/some/dir"
        assert item.pattern == "*.py"
        assert item.recursive is True
        assert item.case_sensitive is False

    def test_default_type(self):
        item = DirectoryReferenceItem(
            path="/dir",
            pattern="*",
            recursive=False,
            case_sensitive=True,
        )
        assert item.type == "directory"

    def test_is_working_set_item_base(self):
        item = DirectoryReferenceItem(
            path="/dir",
            pattern="*",
            recursive=False,
            case_sensitive=True,
        )
        assert isinstance(item, WorkingSetItemBase)


# ---------------------------------------------------------------------------
# DirectoryReferenceItem - render() with file system
# ---------------------------------------------------------------------------


class TestDirectoryReferenceItemRender:
    def test_render_nonexistent_directory(self, tmp_path):
        nonexistent = tmp_path / "no_such_dir"
        item = DirectoryReferenceItem(
            path=str(nonexistent),
            pattern="*",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        assert "does not exist" in result
        assert nonexistent.as_posix() in result

    def test_render_path_is_file(self, tmp_path):
        """If path points to a file, should report it's not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        item = DirectoryReferenceItem(
            path=str(file_path),
            pattern="*",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        assert "is not a directory" in result

    def test_render_empty_directory(self, tmp_path):
        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        assert "Contents of" in result
        assert tmp_path.as_posix() in result
        # Empty dir should have no entries after the header
        # (trailing newline produces an empty string when split)
        non_empty_lines = [l for l in result.split("\n") if l]
        assert len(non_empty_lines) == 1  # Just the header

    def test_render_directory_with_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        (tmp_path / "c.py").write_text("c", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        assert "a.txt" in result
        assert "b.txt" in result
        assert "c.py" in result

    def test_render_directory_with_pattern(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        (tmp_path / "c.py").write_text("c", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*.py",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        assert "c.py" in result
        assert "a.txt" not in result
        assert "b.txt" not in result

    def test_render_non_recursive_excludes_subdirectories(self, tmp_path):
        (tmp_path / "top.txt").write_text("top", encoding="utf-8")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*.txt",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        assert "top.txt" in result
        assert "nested.txt" not in result
        # The subdir itself might appear with pattern "*" but not with "*.txt"

    def test_render_recursive_includes_subdirectories(self, tmp_path):
        (tmp_path / "top.txt").write_text("top", encoding="utf-8")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*.txt",
            recursive=True,
            case_sensitive=True,
        )
        result = item.render()
        assert "top.txt" in result
        assert "nested.txt" in result

    def test_render_case_sensitive(self, tmp_path):
        (tmp_path / "File.TXT").write_text("content", encoding="utf-8")
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*.txt",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        # Case sensitive: only lowercase .txt matches
        assert "file.txt" in result
        assert "File.TXT" not in result

    def test_render_case_insensitive(self, tmp_path):
        (tmp_path / "File.TXT").write_text("content", encoding="utf-8")
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*.txt",
            recursive=False,
            case_sensitive=False,
        )
        result = item.render()
        # Case insensitive: both should match
        assert "File.TXT" in result
        assert "file.txt" in result

    def test_render_pattern_matches_nothing(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*.xyz",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        assert "Contents of" in result
        # No files match
        # (trailing newline produces an empty string when split)
        non_empty_lines = [l for l in result.split("\n") if l]
        assert len(non_empty_lines) == 1  # Just the header

    def test_render_limits_to_max_dir_entries(self, tmp_path):
        """Should only show up to MAX_DIR_ENTRIES (64) entries."""
        # Create more files than MAX_DIR_ENTRIES
        for i in range(MAX_DIR_ENTRIES + 10):
            (tmp_path / f"file_{i:03d}.txt").write_text("x", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*",
            recursive=False,
            case_sensitive=True,
        )
        result = item.render()
        lines = result.split("\n")
        # Header + MAX_DIR_ENTRIES files
        assert len(lines) == MAX_DIR_ENTRIES + 1

    def test_render_recursive_with_deep_nesting(self, tmp_path):
        """Recursive glob should find files in deeply nested directories."""
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_text("deep", encoding="utf-8")

        item = DirectoryReferenceItem(
            path=str(tmp_path),
            pattern="*.txt",
            recursive=True,
            case_sensitive=True,
        )
        result = item.render()
        assert "deep.txt" in result


# ---------------------------------------------------------------------------
# WorkingSetItem type alias - polymorphic validation
# ---------------------------------------------------------------------------


class TestWorkingSetItemTypeAlias:
    def test_validate_text_item(self):
        data = {"type": "text", "text": "Hello"}
        item = working_set_item_adapter.validate_python(data)
        assert isinstance(item, TextItem)
        assert item.text == "Hello"

    def test_validate_file_reference_item(self):
        data = {
            "type": "file",
            "path": "/some/file.txt",
            "start_line": None,
            "end_line": None,
        }
        item = working_set_item_adapter.validate_python(data)
        assert isinstance(item, FileReferenceItem)
        assert item.path == "/some/file.txt"

    def test_validate_directory_reference_item(self):
        data = {
            "type": "directory",
            "path": "/some/dir",
            "pattern": "*.py",
            "recursive": True,
            "case_sensitive": False,
        }
        item = working_set_item_adapter.validate_python(data)
        assert isinstance(item, DirectoryReferenceItem)
        assert item.pattern == "*.py"


# ---------------------------------------------------------------------------
# MAX_DIR_ENTRIES constant
# ---------------------------------------------------------------------------


class TestMaxDirEntries:
    def test_max_dir_entries_is_64(self):
        assert MAX_DIR_ENTRIES == 64
