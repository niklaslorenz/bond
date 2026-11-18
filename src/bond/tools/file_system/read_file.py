from returns.result import Failure

from bond.fs_access import AccessMode
from bond.tools import tool

_DEFAULT_MAX_CHARS = 20_000


def _truncate_output(output: str, max_chars: int, total_lines: int) -> str:
    """
    Hard-cap ``output`` at ``max_chars`` characters, cutting at a line
    boundary when possible and appending a truncation notice.

    The notice itself counts towards the limit, so the returned string is
    guaranteed to be at most ``max_chars`` characters long.
    """
    notice = (
        f"\n... [truncated: output exceeded max_chars={max_chars} "
        f"({total_lines} lines in file; use start_line/end_line to read a "
        f"specific range)]"
    )
    budget = max_chars - len(notice)
    if budget < 0:
        # Not even room for the notice — hard slice
        return output[:max_chars]
    truncated = output[:budget]
    # Prefer cutting at a line boundary so no line is shown half-written
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    return (truncated + notice)[:max_chars]


def _process_file_content(
    content: str,
    start_line: int = 1,
    end_line: int | None = None,
    show_line_numbers: bool = True,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    """
    Process file content based on line range and line number display options.

    Args:
        content: The full file content as a string
        start_line: First line to include (1-indexed), default 1
        end_line: Last line to include (inclusive), optional
        show_line_numbers: Whether to prepend line numbers, default True
        max_chars: Maximum number of characters in the output. If the output
            is longer it is truncated (with a notice). 0 or negative means no
            limit. Default is 20000.

    Returns:
        The processed content string, at most ``max_chars`` characters long
        (if ``max_chars`` > 0)
    """
    all_lines = content.splitlines(keepends=False)

    # Determine which lines to select
    start_idx = start_line - 1
    if end_line is not None:
        selected_lines = all_lines[start_idx:end_line]
    else:
        selected_lines = all_lines[start_idx:]
    line_num_start = start_line

    # Format the output
    if show_line_numbers and selected_lines:
        # Calculate the width needed for line numbers
        max_line_num = line_num_start + len(selected_lines) - 1
        width = len(str(max_line_num))
        result_lines = []
        for i, line in enumerate(selected_lines, start=line_num_start):
            result_lines.append(f"{i:0{width}d}:{line}")
        output = "\n".join(result_lines)
    elif show_line_numbers:
        # No lines to show
        output = ""
    else:
        output = "\n".join(selected_lines)

    if max_chars > 0 and len(output) > max_chars:
        output = _truncate_output(output, max_chars, len(all_lines))
    return output


@tool.tool(
    name="read_file",
    description="""
    Read the contents of the specified file.
    You are only expected to access files inside the current working directory.
    When accessing files outside of the current working directory, the user has to manually grant access.
    You can specify a line range to read.
    The output is capped at max_chars characters (default 20000) and truncated
    with a notice if the file is larger; use start_line/end_line to read a
    specific range of a large file.
    """,
    parameters={
        "file_path": tool.FunctionParameter(
            type="string", description="The path of the file to read."
        ),
        "start_line": tool.FunctionParameter(
            type="integer",
            description="The first line to read (1-indexed). Default is 1.",
        ),
        "end_line": tool.FunctionParameter(
            type="integer",
            description="The last line to read (inclusive). If not provided, reads to end of file.",
        ),
        "show_line_numbers": tool.FunctionParameter(
            type="boolean",
            description="Whether to prepend line numbers to each line. Default is True.",
        ),
        "max_chars": tool.FunctionParameter(
            type="integer",
            description=(
                f"Maximum number of characters to return. Output longer than this is "
                f"truncated with a notice. Use 0 for no limit. Default is {_DEFAULT_MAX_CHARS}."
            ),
        ),
    },
    required=["file_path"],
)
def read_file(
    context: tool.ToolCallContext,
    file_path: str,
    start_line: int = 1,
    end_line: int | None = None,
    show_line_numbers: bool = True,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    grant = context.request_fs_access(file_path, AccessMode.READ)
    if isinstance(grant, Failure):
        return grant.failure()
    authorized = grant.unwrap()
    if not authorized.is_file():
        return "error: not a file"
    content_res = authorized.read_text()
    if isinstance(content_res, Failure):
        return content_res.failure()
    content = content_res.unwrap()
    return _process_file_content(
        content, start_line, end_line, show_line_numbers, max_chars
    )
