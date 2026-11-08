"""Tests for the builtin pdf toolset in bond.tools.pdf_tools."""

import sys
import types
from pathlib import Path

import pytest

from bond.runtime import _default_toolsets
from bond.tools import pdf_tools
from bond.tools.tool import ToolCallContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakePage:
    def __init__(self, text: str | None, fail: bool = False):
        self._text = text
        self._fail = fail

    def extract_text(self):
        if self._fail:
            raise RuntimeError("boom")
        return self._text


class FakePdfReader:
    def __init__(self, path: str, pages: list[FakePage], metadata: dict | None = None):
        self.path = path
        self.pages = pages
        self.metadata = metadata or {}


def install_fake_pypdf(monkeypatch, pages, metadata=None, raise_on_open: bool = False):
    """Install a fake `pypdf` module into sys.modules."""
    fake = types.ModuleType("pypdf")

    def pdf_reader(path: str):
        if raise_on_open:
            raise ValueError("not a pdf")
        return FakePdfReader(path, pages, metadata)

    fake.PdfReader = pdf_reader
    monkeypatch.setitem(sys.modules, "pypdf", fake)
    return fake


def make_context(tmp_path: Path) -> ToolCallContext:
    return ToolCallContext(
        persona=None,
        stdout=None,
        stdin=None,
        is_interactive=False,
        cwd=tmp_path,
        logger=None,
    )


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    return f


# ---------------------------------------------------------------------------
# Toolset registration
# ---------------------------------------------------------------------------


class TestPdfToolsetRegistered:
    def test_pdf_toolset_is_builtin(self):
        toolset_names = [toolset.name for toolset in _default_toolsets]
        assert "pdf" in toolset_names

    def test_pdf_toolset_contains_pdf_info_and_read_pdf_text(self):
        toolset = next(t for t in _default_toolsets if t.name == "pdf")
        names = [tool.function.name for tool in toolset.tool_descriptions]
        assert names == ["pdf_info", "read_pdf_text"]


# ---------------------------------------------------------------------------
# pdf_info
# ---------------------------------------------------------------------------


class TestPdfInfo:
    def test_returns_pages_size_and_metadata(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(
            monkeypatch,
            pages=[FakePage("a"), FakePage("b"), FakePage("c")],
            metadata={"/Title": "My Doc", "/Author": "Ada"},
        )
        out = pdf_tools.pdf_info(make_context(tmp_path), file_path="doc.pdf")
        assert "Pages: 3" in out
        assert "bytes" in out
        assert "Title: My Doc" in out
        assert "Author: Ada" in out
        assert "Subject" not in out  # absent metadata keys are skipped

    def test_missing_pypdf_returns_error(self, monkeypatch, tmp_path, pdf_file):
        monkeypatch.setattr(pdf_tools, "_import_pypdf", lambda: None)
        out = pdf_tools.pdf_info(make_context(tmp_path), file_path="doc.pdf")
        assert out.startswith("Error:")
        assert "pypdf" in out

    def test_not_a_file(self, monkeypatch, tmp_path):
        install_fake_pypdf(monkeypatch, pages=[])
        out = pdf_tools.pdf_info(make_context(tmp_path), file_path="nope.pdf")
        assert out == "Error: not a file: nope.pdf"

    def test_cwd_disabled(self, monkeypatch, pdf_file):
        install_fake_pypdf(monkeypatch, pages=[])
        ctx = make_context(pdf_file.parent)
        ctx.cwd = None
        out = pdf_tools.pdf_info(ctx, file_path="doc.pdf")
        assert "disabled" in out

    def test_unreadable_pdf(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(monkeypatch, pages=[], raise_on_open=True)
        out = pdf_tools.pdf_info(make_context(tmp_path), file_path="doc.pdf")
        assert "could not read PDF" in out


# ---------------------------------------------------------------------------
# read_pdf_text
# ---------------------------------------------------------------------------


class TestReadPdfText:
    def test_extracts_all_pages_with_markers(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(
            monkeypatch, pages=[FakePage("hello"), FakePage("world")]
        )
        out = pdf_tools.read_pdf_text(make_context(tmp_path), file_path="doc.pdf")
        assert "pages 1-2 of 2" in out
        assert "--- page 1 ---\nhello" in out
        assert "--- page 2 ---\nworld" in out

    def test_page_range(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(
            monkeypatch, pages=[FakePage("p1"), FakePage("p2"), FakePage("p3")]
        )
        out = pdf_tools.read_pdf_text(
            make_context(tmp_path), file_path="doc.pdf", start_page=2, end_page=3
        )
        assert "pages 2-3 of 3" in out
        assert "p1" not in out
        assert "--- page 2 ---\np2" in out
        assert "--- page 3 ---\np3" in out

    def test_end_page_clamped_to_page_count(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(monkeypatch, pages=[FakePage("only")])
        out = pdf_tools.read_pdf_text(
            make_context(tmp_path), file_path="doc.pdf", end_page=99
        )
        assert "pages 1-1 of 1" in out
        assert "clamped" in out

    def test_empty_page_gets_placeholder(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(monkeypatch, pages=[FakePage(None), FakePage("")])
        out = pdf_tools.read_pdf_text(make_context(tmp_path), file_path="doc.pdf")
        assert out.count("<no extractable text on this page>") == 2

    def test_page_extraction_error_is_reported(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(monkeypatch, pages=[FakePage("ok"), FakePage(None, fail=True)])
        out = pdf_tools.read_pdf_text(make_context(tmp_path), file_path="doc.pdf")
        assert "--- page 1 ---\nok" in out
        assert "<error extracting page 2: boom>" in out

    def test_truncation(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(monkeypatch, pages=[FakePage("x" * 500)])
        out = pdf_tools.read_pdf_text(
            make_context(tmp_path), file_path="doc.pdf", max_chars=100
        )
        assert "truncated" in out
        assert "max_chars=100" in out

    def test_invalid_page_ranges(self, monkeypatch, tmp_path, pdf_file):
        install_fake_pypdf(monkeypatch, pages=[FakePage("a"), FakePage("b")])
        ctx = make_context(tmp_path)
        assert "start_page must be >= 1" in pdf_tools.read_pdf_text(
            ctx, file_path="doc.pdf", start_page=0
        )
        assert "beyond the last page" in pdf_tools.read_pdf_text(
            ctx, file_path="doc.pdf", start_page=5
        )
        assert "end_page (1) must be >= start_page (2)" in pdf_tools.read_pdf_text(
            ctx, file_path="doc.pdf", start_page=2, end_page=1
        )

    def test_missing_pypdf_returns_error(self, monkeypatch, tmp_path, pdf_file):
        monkeypatch.setattr(pdf_tools, "_import_pypdf", lambda: None)
        out = pdf_tools.read_pdf_text(make_context(tmp_path), file_path="doc.pdf")
        assert out.startswith("Error:")
        assert "pypdf" in out

    def test_not_a_file(self, monkeypatch, tmp_path):
        install_fake_pypdf(monkeypatch, pages=[])
        out = pdf_tools.read_pdf_text(make_context(tmp_path), file_path="nope.pdf")
        assert out == "Error: not a file: nope.pdf"


# ---------------------------------------------------------------------------
# Real pypdf smoke test (skipped if pypdf is not installed)
# ---------------------------------------------------------------------------


class TestRealPypdf:
    def test_read_real_pdf(self, tmp_path):
        pypdf = pytest.importorskip("pypdf")
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=200, height=200)
        f = tmp_path / "blank.pdf"
        with f.open("wb") as fh:
            writer.write(fh)
        ctx = make_context(tmp_path)
        info = pdf_tools.pdf_info(ctx, file_path="blank.pdf")
        assert "Pages: 1" in info
        text = pdf_tools.read_pdf_text(ctx, file_path="blank.pdf")
        assert "pages 1-1 of 1" in text
