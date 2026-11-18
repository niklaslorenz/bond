"""Tests for the read_file tool, in particular the max_chars output cap."""

from pathlib import Path

from bond.tools.file_system.read_file import (
    _DEFAULT_MAX_CHARS,
    _process_file_content,
    read_file,
)
from bond.tools.tool import ToolCallContext


def make_context(tmp_path: Path) -> ToolCallContext:
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=tmp_path,
        logger=None,
        confirmation_prompt=lambda prompt: True,
        conversation=None,
    )


class TestProcessFileContent:
    def test_small_output_not_truncated(self):
        content = "alpha\nbeta\ngamma\n"
        out = _process_file_content(content, max_chars=1000)
        assert "1:alpha" in out
        assert "3:gamma" in out
        assert "truncated" not in out

    def test_output_capped_at_max_chars(self):
        content = "\n".join(f"line {i} " + "x" * 50 for i in range(1, 101))
        max_chars = 500
        out = _process_file_content(content, max_chars=max_chars)
        assert len(out) <= max_chars
        assert "truncated" in out
        assert f"max_chars={max_chars}" in out
        assert "100 lines in file" in out

    def test_truncation_cuts_at_line_boundary(self):
        # Each formatted line is "N:aaa..." — after truncation no partial
        # line should appear right before the notice.
        content = "\n".join("a" * 40 for _ in range(50))
        max_chars = 300
        out = _process_file_content(content, max_chars=max_chars)
        assert len(out) <= max_chars
        notice_idx = out.index("... [truncated")
        before_notice = out[:notice_idx]
        # everything before the notice must be complete numbered lines
        for line in before_notice.split("\n"):
            assert line == "" or (line.split(":", 1)[1] == "a" * 40)

    def test_max_chars_zero_means_no_limit(self):
        content = "x" * 100_000
        out = _process_file_content(content, max_chars=0)
        assert len(out) > 100_000  # line number prefix adds chars
        assert "truncated" not in out

    def test_tiny_max_chars_still_hard_capped(self):
        # Even if the notice alone is longer than max_chars, the output must
        # not exceed max_chars.
        content = "y" * 10_000
        out = _process_file_content(content, max_chars=10)
        assert len(out) <= 10

    def test_line_range_still_applies_with_cap(self):
        content = "\n".join(f"row {i}" for i in range(1, 1001))
        out = _process_file_content(content, start_line=500, end_line=510, max_chars=1000)
        assert "500:row 500" in out
        assert "510:row 510" in out
        assert "truncated" not in out

    def test_no_line_numbers_mode_respects_cap(self):
        content = "\n".join("b" * 100 for _ in range(200))
        out = _process_file_content(content, show_line_numbers=False, max_chars=1000)
        assert len(out) <= 1000
        assert "truncated" in out


class TestReadFileTool:
    def test_default_cap_on_huge_file(self, tmp_path: Path):
        big = tmp_path / "big.txt"
        big.write_text("z" * 500_000, encoding="utf-8")
        result = read_file(make_context(tmp_path), str(big))
        assert len(result) <= _DEFAULT_MAX_CHARS
        assert "truncated" in result

    def test_small_file_unaffected_by_default(self, tmp_path: Path):
        small = tmp_path / "small.txt"
        small.write_text("hello\nworld\n", encoding="utf-8")
        result = read_file(make_context(tmp_path), str(small))
        assert "1:hello" in result
        assert "2:world" in result
        assert "truncated" not in result

    def test_explicit_max_chars(self, tmp_path: Path):
        f = tmp_path / "f.txt"
        f.write_text("\n".join("c" * 80 for _ in range(100)), encoding="utf-8")
        result = read_file(make_context(tmp_path), str(f), max_chars=400)
        assert len(result) <= 400
        assert "truncated" in result

    def test_max_chars_zero_disables_cap(self, tmp_path: Path):
        f = tmp_path / "f.txt"
        f.write_text("d" * 50_000, encoding="utf-8")
        result = read_file(make_context(tmp_path), str(f), max_chars=0)
        assert "d" * 50_000 in result
        assert "truncated" not in result

    def test_schema_exposes_max_chars(self):
        params = read_file.description.function.parameters  # type: ignore[attr-defined]
        assert "max_chars" in params.properties
        assert "file_path" in params.required
        assert "max_chars" not in params.required
