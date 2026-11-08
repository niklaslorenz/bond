"""PDF reading tools for Bond skills.

Copy this file into your skill's ``tools/`` directory::

    skills/pdf/tools/pdf_tools.py

and load the skill. The tools below become available with names prefixed by
``sk:<skill-name>:`` (e.g. ``sk:pdf:read_pdf_text``).

Requires the ``pypdf`` package: ``pip install pypdf`` (or ``pip install bond[pdf]``).
The import is lazy, so the file only fails (with a clear error message) when a
PDF tool is actually called without ``pypdf`` installed.
"""

from pathlib import Path
from typing import Any

from bond.tools import tool
from bond.tools.file_system.util import check_access
from bond.tools.toolbox import PythonToolset
from bond.util import resolve_path

_PYPDF_MISSING = (
    "Error: the 'pypdf' package is required for PDF tools but is not installed. "
    "Install it with `pip install pypdf` (or `pip install bond[pdf]`)."
)

_DEFAULT_MAX_CHARS = 20_000


def _import_pypdf() -> Any:
    """Import pypdf lazily; returns None if it is not installed."""
    try:
        import pypdf
    except ImportError:
        return None
    return pypdf


def _resolve_pdf_path(
    context: tool.ToolCallContext, file_path: str
) -> tuple[Path | None, str]:
    """Resolve ``file_path`` against the cwd and check access.

    Returns ``(path, "")`` on success or ``(None, error_message)``.
    """
    if context.cwd is None:
        return None, "Error: Tool access to the file system is currently disabled."
    path = resolve_path(context.cwd, Path(file_path))
    has_access, why_not = check_access(context, path)
    if not has_access:
        return None, why_not
    if not path.is_file():
        return None, f"Error: not a file: {file_path}"
    return path, ""


def _open_pdf(pypdf: Any, path: Path) -> tuple[Any, str]:
    """Open a PDF with pypdf; returns ``(reader, "")`` or ``(None, error)``."""
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as e:
        return None, f"Error: could not read PDF '{path.name}': {e}"
    return reader, ""


@tool.tool(
    name="pdf_info",
    description="""
    Get information about a PDF file: page count, file size, and metadata
    (title, author, subject, creator, producer, creation date).
    Use this first to find out how many pages a PDF has before reading it.
    """,
    parameters={
        "file_path": tool.FunctionParameter(
            type="string",
            description="Path to the PDF file (absolute or relative to the current working directory).",
        ),
    },
    required=["file_path"],
)
def pdf_info(context: tool.ToolCallContext, file_path: str) -> str:
    pypdf = _import_pypdf()
    if pypdf is None:
        return _PYPDF_MISSING
    path, err = _resolve_pdf_path(context, file_path)
    if path is None:
        return err
    reader, err = _open_pdf(pypdf, path)
    if reader is None:
        return err

    metadata = reader.metadata or {}
    lines = [
        f"File: {path}",
        f"Size: {path.stat().st_size} bytes",
        f"Pages: {len(reader.pages)}",
    ]
    for key, label in [
        ("/Title", "Title"),
        ("/Author", "Author"),
        ("/Subject", "Subject"),
        ("/Creator", "Creator"),
        ("/Producer", "Producer"),
        ("/CreationDate", "Creation date"),
    ]:
        value = metadata.get(key)
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


@tool.tool(
    name="read_pdf_text",
    description="""
    Extract the text content of a PDF file, page by page.
    Pages are returned with '--- page N ---' markers. You can limit the output
    to a page range (1-indexed, inclusive) and to a maximum number of characters.
    Call pdf_info first if you need to know the page count.
    Note: text extraction only works for PDFs with a text layer; scanned
    documents return empty page text.
    """,
    parameters={
        "file_path": tool.FunctionParameter(
            type="string",
            description="Path to the PDF file (absolute or relative to the current working directory).",
        ),
        "start_page": tool.FunctionParameter(
            type="integer",
            description="First page to extract (1-indexed). Default is 1.",
        ),
        "end_page": tool.FunctionParameter(
            type="integer",
            description="Last page to extract (1-indexed, inclusive). If not provided, reads to the last page.",
        ),
        "max_chars": tool.FunctionParameter(
            type="integer",
            description=f"Maximum number of characters to return. Default is {_DEFAULT_MAX_CHARS}.",
        ),
    },
    required=["file_path"],
)
def read_pdf_text(
    context: tool.ToolCallContext,
    file_path: str,
    start_page: int = 1,
    end_page: int | None = None,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    pypdf = _import_pypdf()
    if pypdf is None:
        return _PYPDF_MISSING
    path, err = _resolve_pdf_path(context, file_path)
    if path is None:
        return err
    reader, err = _open_pdf(pypdf, path)
    if reader is None:
        return err

    page_count = len(reader.pages)
    if start_page < 1:
        return f"Error: start_page must be >= 1, got {start_page}."
    if start_page > page_count:
        return (
            f"Error: start_page {start_page} is beyond the last page "
            f"({page_count}) of '{path.name}'."
        )
    last_page = min(end_page, page_count) if end_page is not None else page_count
    if end_page is not None and end_page < start_page:
        return (
            f"Error: end_page ({end_page}) must be >= start_page ({start_page})."
        )

    chunks: list[str] = []
    for page_number in range(start_page, last_page + 1):
        page = reader.pages[page_number - 1]
        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = f"<error extracting page {page_number}: {e}>"
        text = text.strip()
        if not text:
            text = "<no extractable text on this page>"
        chunks.append(f"--- page {page_number} ---\n{text}")

    output = "\n\n".join(chunks)
    if max_chars > 0 and len(output) > max_chars:
        output = (
            output[:max_chars]
            + f"\n\n... [truncated: output exceeded max_chars={max_chars}, "
            f"showing first {max_chars} of the extracted text]"
        )
    header = f"{path.name}: pages {start_page}-{last_page} of {page_count}"
    if end_page is not None and end_page > page_count:
        header += f" (end_page {end_page} clamped to page count)"
    return f"{header}\n\n{output}"


EXPORT_TOOLSETS = [
    PythonToolset("pdf", [pdf_info, read_pdf_text]),
]
