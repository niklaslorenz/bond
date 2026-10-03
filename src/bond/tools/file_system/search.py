"""File search tool."""

import re
from pathlib import Path

from bond.tools import tool
from bond.util import resolve_path

from .util import check_access, fuzzy_contains


@tool.tool(
    name="search_file",
    description="""
    Search for content in a file.
    You are only expected to access files inside the current working directory.
    When accessing files outside of the current working directory, the user has to manually grant access.
    
    Supports literal string matching, regular expressions, and fuzzy matching.
    """,
    parameters={
        "file_path": tool.FunctionParameter(
            type="string", description="The path of the file to search in."
        ),
        "pattern": tool.FunctionParameter(
            type="string", description="The text or regex pattern to search for."
        ),
        "use_regex": tool.FunctionParameter(
            type="boolean",
            description="Whether to treat pattern as a regular expression. Default is False.",
        ),
        "case_sensitive": tool.FunctionParameter(
            type="boolean",
            description="Whether the search should be case-sensitive. Default is True.",
        ),
        "fuzzy_match": tool.FunctionParameter(
            type="boolean",
            description="Whether to use fuzzy matching. Default is False.",
        ),
        "show_line_numbers": tool.FunctionParameter(
            type="boolean",
            description="Whether to prepend line numbers to matching lines. Default is True.",
        ),
        "context_lines": tool.FunctionParameter(
            type="integer",
            description="Number of lines before/after each match to show for context. Default is 0.",
        ),
    },
    required=["file_path", "pattern"],
)
def search_file(
    context: tool.ToolCallContext,
    file_path: str,
    pattern: str,
    use_regex: bool = False,
    case_sensitive: bool = True,
    fuzzy_match: bool = False,
    show_line_numbers: bool = True,
    context_lines: int = 0,
) -> str:
    if context.cwd is None:
        return "Error: Tool access to the filesystem is currently disabled."

    path = resolve_path(context.cwd, Path(file_path))
    has_access, why_not = check_access(context, path)
    if not has_access:
        return why_not
    if not path.is_file():
        return "error: not a file"

    content = path.read_text()
    lines = content.splitlines(keepends=False)

    if not lines:
        return "No matches found (file is empty)"

    matches: list[tuple[int, str]] = []  # (line_number, line_content)

    if fuzzy_match:
        for i, line in enumerate(lines, start=1):
            if fuzzy_contains(line, pattern):
                matches.append((i, line))
    elif use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"Error: invalid regular expression: {str(e)}"

        for i, line in enumerate(lines, start=1):
            if regex.search(line):
                matches.append((i, line))
    else:
        if not case_sensitive:
            pattern_lower = pattern.lower()
            for i, line in enumerate(lines, start=1):
                if pattern_lower in line.lower():
                    matches.append((i, line))
        else:
            for i, line in enumerate(lines, start=1):
                if pattern in line:
                    matches.append((i, line))

    if not matches:
        return "No matches found"

    # Build the result
    result_lines: list[str] = []

    for line_num, line_content in matches:
        # Add context lines before the match
        if context_lines > 0:
            start_context = max(1, line_num - context_lines)
            for ctx_num in range(start_context, line_num):
                if ctx_num < len(lines) + 1:
                    prefix = f"{ctx_num}:" if show_line_numbers else ""
                    result_lines.append(f"{prefix}{lines[ctx_num-1]}")

        # Add the matching line
        prefix = f"{line_num}:" if show_line_numbers else ""
        result_lines.append(f"{prefix}{line_content}")

        # Add context lines after the match
        if context_lines > 0:
            end_context = min(len(lines), line_num + context_lines)
            for ctx_num in range(line_num + 1, end_context + 1):
                prefix = f"{ctx_num}:" if show_line_numbers else ""
                result_lines.append(f"{prefix}{lines[ctx_num-1]}")

        # Add separator between match groups
        if context_lines > 0:
            result_lines.append("---")

    return "\n".join(result_lines)