"""Builtin PDF tools, registered as the ``pdf`` toolset in the runtime.

Requires the ``pypdf`` package: ``pip install pypdf`` (or ``pip install bond[pdf]``).
The import is lazy, so the tools only fail (with a clear error message) when a
PDF tool is actually called without ``pypdf`` installed.
"""

import io
from typing import Any

from returns.result import Failure, Success

from bond.fs_access import AccessMode, AuthorizedPath
from bond.tools import tool

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
) -> tuple[AuthorizedPath | None, str]:
    """Resolve ``file_path`` (incl. ``bond://`` URIs) and authorize read access.

    Returns ``(authorized_path, "")`` on success or ``(None, error_message)``.
    """
    grant = context.request_fs_access(file_path, AccessMode.READ)
    if isinstance(grant, Failure):
        return None, grant.failure()
    authorized = grant.unwrap()
    if not authorized.is_file():
        return None, f"Error: not a file: {file_path}"
    return authorized, ""


def _open_pdf(pypdf: Any, authorized: AuthorizedPath) -> tuple[Any, str]:
    """Open a PDF with pypdf; returns ``(reader, "")`` or ``(None, error)``.

    The file content goes through the authorized wrapper and is handed to
    pypdf as a stream, so pypdf never opens the path itself.
    """
    data_res = authorized.read_bytes()
    if isinstance(data_res, Failure):
        return None, data_res.failure()
    try:
        reader = pypdf.PdfReader(io.BytesIO(data_res.unwrap()))
    except Exception as e:
        return None, f"Error: could not read PDF '{authorized.path.name}': {e}"
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
    authorized, err = _resolve_pdf_path(context, file_path)
    if authorized is None:
        return err
    reader, err = _open_pdf(pypdf, authorized)
    if reader is None:
        return err

    stat_res = authorized.stat()
    size = stat_res.unwrap().st_size if isinstance(stat_res, Success) else 0
    metadata = reader.metadata or {}
    lines = [
        f"File: {authorized.path}",
        f"Size: {size} bytes",
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
    authorized, err = _resolve_pdf_path(context, file_path)
    if authorized is None:
        return err
    reader, err = _open_pdf(pypdf, authorized)
    if reader is None:
        return err

    page_count = len(reader.pages)
    path_name = authorized.path.name
    if start_page < 1:
        return f"Error: start_page must be >= 1, got {start_page}."
    if start_page > page_count:
        return (
            f"Error: start_page {start_page} is beyond the last page "
            f"({page_count}) of '{path_name}'."
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
    header = f"{path_name}: pages {start_page}-{last_page} of {page_count}"
    if end_page is not None and end_page > page_count:
        header += f" (end_page {end_page} clamped to page count)"
    return f"{header}\n\n{output}"
