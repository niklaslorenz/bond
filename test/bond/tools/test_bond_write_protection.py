"""Tests for the .bond write protection in the file system tools."""

from pathlib import Path

from bond.tools.file_system.apply_patch import apply_patch
from bond.tools.file_system.create_file import create_file
from bond.tools.file_system.read_file import read_file
from bond.tools.file_system.util import check_write_access, path_is_in_bond
from bond.tools.tool import ToolCallContext


def make_context(tmp_path: Path, is_interactive: bool = False) -> ToolCallContext:
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=is_interactive,
        cwd=tmp_path,
        logger=None,
        confirmation_prompt=lambda prompt: True,
        conversation=None,
    )


class TestPathIsInBond:
    def test_detects_bond_dirs(self):
        assert path_is_in_bond(Path("/x/.bond/y"))
        assert path_is_in_bond(Path("/x/.bond"))
        assert path_is_in_bond(Path("a/.bond/b"))
        assert not path_is_in_bond(Path("/x/bond/y"))
        assert not path_is_in_bond(Path("/x/.bondx/y"))


class TestCheckWriteAccess:
    def test_bond_path_denied(self, tmp_path: Path):
        ok, msg = check_write_access(make_context(tmp_path), tmp_path / ".bond" / "x")
        assert not ok
        assert "read-only" in msg

    def test_normal_path_allowed(self, tmp_path: Path):
        ok, msg = check_write_access(make_context(tmp_path), tmp_path / "normal")
        assert ok
        assert msg == ""


class TestCreateFile:
    def test_create_in_bond_denied(self, tmp_path: Path):
        target = tmp_path / ".bond" / "scripts" / "x"
        result = create_file(make_context(tmp_path), str(target), "content")
        assert "Permission denied" in result
        assert "read-only" in result
        assert not target.exists()

    def test_create_normal_file_ok(self, tmp_path: Path):
        target = tmp_path / "x.txt"
        result = create_file(make_context(tmp_path), str(target), "content")
        assert "Created file at" in result
        assert target.read_text(encoding="utf-8") == "content"


class TestApplyPatch:
    def test_patch_in_bond_denied(self, tmp_path: Path):
        target = tmp_path / ".bond" / "keep.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("keep\n", encoding="utf-8")
        patch = (
            ".bond/keep.md\n"
            "<<<<<<< SEARCH\n"
            "keep\n"
            "=======\n"
            "changed\n"
            ">>>>>>> REPLACE"
        )
        result = apply_patch(make_context(tmp_path, is_interactive=True), patch)
        assert "inside a .bond folder" in result
        assert target.read_text(encoding="utf-8") == "keep\n"

    def test_patch_normal_file_ok(self, tmp_path: Path):
        target = tmp_path / "keep.md"
        target.write_text("keep\n", encoding="utf-8")
        patch = (
            "keep.md\n"
            "<<<<<<< SEARCH\n"
            "keep\n"
            "=======\n"
            "changed\n"
            ">>>>>>> REPLACE"
        )
        result = apply_patch(make_context(tmp_path), patch)
        assert "success" in result
        assert target.read_text(encoding="utf-8") == "changed\n"


class TestReadFile:
    def test_read_in_bond_still_allowed(self, tmp_path: Path):
        target = tmp_path / ".bond" / "keep.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content", encoding="utf-8")
        result = read_file(make_context(tmp_path), str(target))
        assert "content" in result
