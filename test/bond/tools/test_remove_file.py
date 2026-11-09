"""Tests for the remove_file tool."""

from pathlib import Path

from bond.tools.file_system.remove_file import remove_file
from bond.tools.tool import ToolCallContext


def make_context(
    tmp_path: Path, confirm: bool = True, is_interactive: bool = False
) -> ToolCallContext:
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=is_interactive,
        cwd=tmp_path,
        logger=None,
        confirmation_prompt=lambda prompt: confirm,
        conversation=None,
    )


class TestRemoveFile:
    def test_removes_existing_file(self, tmp_path: Path):
        target = tmp_path / "x.txt"
        target.write_text("data", encoding="utf-8")
        # no .git in tmp_path -> confirmation asked, granted by make_context
        result = remove_file(make_context(tmp_path), "x.txt")
        assert "Removed file" in result
        assert not target.exists()

    def test_missing_file(self, tmp_path: Path):
        result = remove_file(make_context(tmp_path), "nope.txt")
        assert "does not exist" in result

    def test_directory_refused(self, tmp_path: Path):
        (tmp_path / "somedir").mkdir()
        result = remove_file(make_context(tmp_path), "somedir")
        assert "directory" in result
        assert (tmp_path / "somedir").is_dir()

    def test_symlink_removes_link_not_target(self, tmp_path: Path):
        target = tmp_path / "target.txt"
        target.write_text("keep me", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        result = remove_file(make_context(tmp_path), "link.txt")
        assert "Removed file" in result
        assert not link.exists() and not link.is_symlink()
        assert target.read_text(encoding="utf-8") == "keep me"

    def test_git_repo_skips_confirmation(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        target = tmp_path / "tracked.txt"
        target.write_text("data", encoding="utf-8")
        # confirmation declined, but inside a git repo it is skipped
        result = remove_file(make_context(tmp_path, confirm=False), "tracked.txt")
        assert "Removed file" in result
        assert not target.exists()

    def test_confirmation_declined_cancels(self, tmp_path: Path):
        target = tmp_path / "x.txt"
        target.write_text("data", encoding="utf-8")
        result = remove_file(make_context(tmp_path, confirm=False), "x.txt")
        assert "cancelled" in result
        assert target.exists()

    def test_git_dir_denied(self, tmp_path: Path):
        target = tmp_path / ".git" / "HEAD"
        target.parent.mkdir(parents=True)
        target.write_text("ref: refs/heads/main", encoding="utf-8")
        result = remove_file(make_context(tmp_path), ".git/HEAD")
        assert "Permission denied" in result
        assert "`.git`" in result and "read-only" in result
        assert target.exists()

    def test_bond_dir_denied(self, tmp_path: Path):
        target = tmp_path / ".bond" / "keep.md"
        target.parent.mkdir(parents=True)
        target.write_text("keep", encoding="utf-8")
        result = remove_file(make_context(tmp_path), ".bond/keep.md")
        assert "Permission denied" in result
        assert "`.bond`" in result and "read-only" in result
        assert target.exists()

    def test_outside_cwd_denied_non_interactive(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "x.txt"
        target.write_text("data", encoding="utf-8")
        other = tmp_path / "work"
        other.mkdir()
        result = remove_file(make_context(other), str(target))
        assert "Permission denied" in result
        assert target.exists()
