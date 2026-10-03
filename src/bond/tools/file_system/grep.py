"""Multi-file grep-like search tool using system grep/ripgrep."""

import shutil
import subprocess
from pathlib import Path

from bond.tools import tool
from bond.tools.file_system.util import check_access
from bond.util import resolve_path


def _build_grep_command(
    pattern: str,
    path: Path,
    use_regex: bool,
    case_sensitive: bool,
    recursive: bool,
    context_lines: int,
    show_line_numbers: bool,
    use_ripgrep: bool,
) -> list[str]:
    """Build the grep/rg command line arguments."""
    cmd = []

    if use_ripgrep:
        cmd.append("rg")
        # ripgrep is recursive by default
        if not recursive:
            cmd.append("--no-recursive")
        if use_regex:
            cmd.append("-P")  # PCRE regex
        if not case_sensitive:
            cmd.append("-i")
        if show_line_numbers:
            cmd.append("-n")
        if context_lines > 0:
            cmd.append(f"-C{context_lines}")
        # Always show filenames and disable color
        cmd.extend(["--color=never", "--hidden"])
    else:
        cmd.append("grep")
        if recursive:
            cmd.append("-r")
        if use_regex:
            # Use Perl-compatible regex if available, otherwise extended
            cmd.append("-P")
        if not case_sensitive:
            cmd.append("-i")
        if show_line_numbers:
            cmd.append("-n")
        if context_lines > 0:
            cmd.append(f"-C{context_lines}")
        # Always show filenames and disable color
        cmd.extend(["-H", "--color=never"])

    # Add pattern and path
    cmd.append(pattern)
    cmd.append(str(path))

    return cmd


@tool.tool(
    name="grep",
    description="""
    Search for a pattern across multiple files using system grep or ripgrep.
    You are only expected to access locations inside the current working directory.
    When accessing paths outside of the current working directory, the user has to manually grant access.
    
    Requires grep or ripgrep (rg) to be installed on the system.
    Supports literal string matching and regular expressions.
    Searches recursively through directories by default.
    """,
    parameters={
        "pattern": tool.FunctionParameter(
            type="string", description="The text or regex pattern to search for."
        ),
        "path": tool.FunctionParameter(
            type="string", description="File or directory path to search in."
        ),
        "use_regex": tool.FunctionParameter(
            type="boolean",
            description="Whether to treat pattern as a regular expression. Default is False.",
        ),
        "case_sensitive": tool.FunctionParameter(
            type="boolean",
            description="Whether the search should be case-sensitive. Default is True.",
        ),
        "recursive": tool.FunctionParameter(
            type="boolean",
            description="Whether to search recursively in directories. Default is True.",
        ),
        "context_lines": tool.FunctionParameter(
            type="integer",
            description="Number of lines before/after each match to show for context. Default is 0.",
        ),
        "show_line_numbers": tool.FunctionParameter(
            type="boolean",
            description="Whether to prepend line numbers to matching lines. Default is True.",
        ),
    },
    required=["pattern", "path"],
)
def grep(
    context: tool.ToolCallContext,
    pattern: str,
    path: str,
    use_regex: bool = False,
    case_sensitive: bool = True,
    recursive: bool = True,
    context_lines: int = 0,
    show_line_numbers: bool = True,
) -> str:
    if context.cwd is None:
        return "Error: Tool access to the filesystem is currently disabled."

    search_path = resolve_path(context.cwd, Path(path))
    has_access, why_not = check_access(context, search_path)
    if not has_access:
        return why_not

    if not search_path.exists():
        return f"Error: path does not exist: {search_path}"

    # Check for ripgrep first, then grep
    use_ripgrep = shutil.which("rg") is not None
    use_grep = not use_ripgrep and shutil.which("grep") is not None

    if not use_ripgrep and not use_grep:
        return (
            "Error: Neither ripgrep (rg) nor grep is available on this system. "
            "Unless the user installs at least one of them, this tool does not work."
        )

    # Build command
    cmd = _build_grep_command(
        pattern=pattern,
        path=search_path,
        use_regex=use_regex,
        case_sensitive=case_sensitive,
        recursive=recursive,
        context_lines=context_lines,
        show_line_numbers=show_line_numbers,
        use_ripgrep=use_ripgrep,
    )

    # Execute command
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(context.cwd),
        )

        if result.returncode == 0:
            if result.stdout:
                return result.stdout.rstrip()
            return "No matches found."
        elif result.returncode == 1:
            # grep/rg returns 1 when no matches found
            return "No matches found."
        else:
            return f"Error: grep/rg failed with exit code {result.returncode}: {result.stderr}"

    except Exception as e:
        return f"Error: Failed to execute grep/rg: {str(e)}"
