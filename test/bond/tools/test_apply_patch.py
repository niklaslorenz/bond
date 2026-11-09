"""Tests for apply_patch result snippets (changed region with context)."""

from pathlib import Path

from bond.tools.file_system.apply_patch import (
    CONTEXT_LINES,
    MAX_SNIPPET_CHANGED_LINES,
    apply_patch,
)
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


def make_patch(file: str, search: str, replace: str) -> str:
    return (
        f"{file}\n"
        "<<<<<<< SEARCH\n"
        f"{search}\n"
        "=======\n"
        f"{replace}\n"
        ">>>>>>> REPLACE"
    )


class TestExactMatchSnippet:
    def test_snippet_shows_changed_line_with_context(self, tmp_path: Path):
        target = tmp_path / "f.txt"
        target.write_text("\n".join(f"line {i}" for i in range(1, 11)) + "\n")
        result = apply_patch(
            make_context(tmp_path), make_patch("f.txt", "line 5", "CHANGED")
        )
        assert "Block 0: success — f.txt (changed lines 5-5)" in result
        assert "> 5: CHANGED" in result
        # context lines before and after, not marked
        for i in range(5 - CONTEXT_LINES, 5):
            assert f"  {i}: line {i}" in result
        for i in range(6, 6 + CONTEXT_LINES):
            assert f"  {i}: line {i}" in result
        # file was actually changed
        assert "CHANGED" in target.read_text(encoding="utf-8")

    def test_multi_line_replacement_reports_line_range(self, tmp_path: Path):
        target = tmp_path / "f.txt"
        target.write_text("a\nb\nc\nd\ne\n")
        result = apply_patch(
            make_context(tmp_path), make_patch("f.txt", "b\nc", "x\ny\nz")
        )
        assert "(changed lines 2-4)" in result
        assert "> 2: x" in result
        assert "> 3: y" in result
        assert "> 4: z" in result
        assert "  5: d" in result
        assert "  6: e" in result

    def test_deletion_reports_deletion_line_without_markers(self, tmp_path: Path):
        target = tmp_path / "f.txt"
        target.write_text("a\nb\nc\nd\ne\n")
        result = apply_patch(make_context(tmp_path), make_patch("f.txt", "c", ""))
        assert "(deletion at line 3)" in result
        assert ">" not in result.split("success — f.txt")[1].split("Modified files")[0]
        # "c" is removed without its newline, leaving an empty line
        assert target.read_text(encoding="utf-8") == "a\nb\n\nd\ne\n"


class TestFuzzyMatchSnippet:
    def test_fuzzy_match_still_returns_snippet(self, tmp_path: Path):
        target = tmp_path / "f.py"
        target.write_text(
            "def foo():\n    x = 1\n    return x\n\ndef bar():\n    pass\n"
        )
        # not an exact match (return y vs return x), but fuzzy-matches
        result = apply_patch(
            make_context(tmp_path),
            make_patch("f.py", "def foo():\n    x = 1\n    return y", "def foo():\n    x = 2\n    return x"),
        )
        assert "Block 0: success" in result
        assert "(changed lines 1-3)" in result
        assert "> 2:     x = 2" in result


class TestMultipleBlocks:
    def test_each_block_gets_own_snippet(self, tmp_path: Path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("a1\na2\na3\n")
        b.write_text("b1\nb2\nb3\n")
        patch = make_patch("a.txt", "a2", "A2") + "\n\n" + make_patch("b.txt", "b2", "B2")
        result = apply_patch(make_context(tmp_path), patch)
        assert "Block 0: success — a.txt (changed lines 2-2)" in result
        assert "> 2: A2" in result
        assert "Block 1: success — b.txt (changed lines 2-2)" in result
        assert "> 2: B2" in result
        assert "Modified files:" in result


class TestFailureCases:
    def test_failed_block_has_no_snippet_and_file_unchanged(self, tmp_path: Path):
        target = tmp_path / "f.txt"
        target.write_text("hello\n")
        result = apply_patch(
            make_context(tmp_path), make_patch("f.txt", "nonexistent", "x")
        )
        assert "Block 0: failed, search term not found" in result
        assert ">" not in result
        assert target.read_text(encoding="utf-8") == "hello\n"


class TestSnippetCap:
    def test_large_replacement_is_capped(self, tmp_path: Path):
        target = tmp_path / "f.txt"
        target.write_text("start\nmiddle\nend\n")
        replace = "\n".join(f"new {i}" for i in range(MAX_SNIPPET_CHANGED_LINES + 10))
        result = apply_patch(
            make_context(tmp_path), make_patch("f.txt", "middle", replace)
        )
        assert f"({10} more changed lines)" in result
        # capped: not all changed lines are shown
        assert f"> {2 + MAX_SNIPPET_CHANGED_LINES + 9}:" not in result
