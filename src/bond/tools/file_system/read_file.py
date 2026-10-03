from pathlib import Path

from bond.tools import tool
from bond.tools.file_system.util import check_access
from bond.util import resolve_path


def _process_file_content(
    content: str,
    start_line: int = 1,
    end_line: int | None = None,
    show_line_numbers: bool = True,
) -> str:
    """
    Process file content based on line range and line number display options.

    Args:
        content: The full file content as a string
        start_line: First line to include (1-indexed), default 1
        end_line: Last line to include (inclusive), optional
        show_line_numbers: Whether to prepend line numbers, default True

    Returns:
        The processed content string
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
        return "\n".join(result_lines)
    elif show_line_numbers:
        # No lines to show
        return ""
    else:
        return "\n".join(selected_lines)


@tool.tool(
    name="read_file",
    description="""
    Read the contents of the specified file.
    You are only expected to access files inside the current working directory.
    When accessing files outside of the current working directory, the user has to manually grant access.
    You can specify a line range to read.
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
    },
    required=["file_path"],
)
def read_file(
    context: tool.ToolCallContext,
    file_path: str,
    start_line: int = 1,
    end_line: int | None = None,
    show_line_numbers: bool = True,
) -> str:
    if context.cwd is None:
        return "Error: Tool access to the file system is currently disabled."
    path = resolve_path(context.cwd, Path(file_path))
    has_access, why_not = check_access(context, path)
    if not has_access:
        return why_not
    if not path.is_file():
        return "error: not a file"
    content = path.read_text()
    return _process_file_content(content, start_line, end_line, show_line_numbers)
