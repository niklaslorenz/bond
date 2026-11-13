"""Recursive directory tree listing tool."""

import os
from pathlib import Path

from bond.tools import tool
from bond.tools.file_system.util import check_access

# Hard cap on displayed lines; anything beyond is omitted with a notice.
MAX_TREE_LINES = 200

DEFAULT_MAX_DEPTH = 3


def _tree_lines(path: Path, prefix: str, depth: int, max_depth: int) -> list[str]:
    """Build the tree lines for the entries of ``path`` at the given depth.

    Symlinked directories are shown as ``name -> target`` and never recursed
    into, so symlink cycles cannot blow up the listing.
    """
    if depth > max_depth:
        return []
    try:
        with os.scandir(path) as it:
            entries = sorted(
                list(it),
                key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
            )
    except (PermissionError, OSError) as e:
        return [f"{prefix}[error: {e}]"]

    lines: list[str] = []
    for i, entry in enumerate(entries):
        last = i == len(entries) - 1
        connector = "└── " if last else "├── "
        if entry.is_symlink():
            try:
                target = os.readlink(entry.path)
            except OSError:
                target = "?"
            lines.append(f"{prefix}{connector}{entry.name} -> {target}")
            continue
        if entry.is_dir(follow_symlinks=False):
            lines.append(f"{prefix}{connector}{entry.name}/")
            extension = "    " if last else "│   "
            lines.extend(
                _tree_lines(
                    Path(entry.path), prefix + extension, depth + 1, max_depth
                )
            )
        else:
            lines.append(f"{prefix}{connector}{entry.name}")
    return lines


@tool.tool(
    name="tree",
    description="""
    List a directory recursively as a tree (like the `tree` command).
    You are only expected to access locations inside the current working directory.
    When accessing paths outside of the current working directory, the user has to manually grant access.

    Directories are shown with a trailing '/', symlinks as 'name -> target' (never followed).
    At most 200 lines are displayed; if there are more, a notice at the end says how many lines were omitted.

    Args:
        dir_path (str): The path of the directory to list.
        max_depth (int): How many levels below the root to descend (0 = only the root itself). Default is 3.

    Returns:
        str: The tree of the directory
    """,
    parameters={
        "dir_path": tool.FunctionParameter(
            type="string", description="directory path (absolute or relative to cwd)"
        ),
        "max_depth": tool.FunctionParameter(
            type="integer",
            description="Maximum number of levels below the root to display. Default is 3.",
        ),
    },
    required=["dir_path"],
)
def tree(
    context: tool.ToolCallContext, dir_path: str, max_depth: int = DEFAULT_MAX_DEPTH
) -> str:
    try:
        path = context.resolve_path(dir_path)
    except ValueError as e:
        return f"Error: {e}"
    if path is None:
        return "Error: Tool access to the filesystem is currently disabled."
    has_access, why_not = check_access(context, path)
    if not has_access:
        return why_not
    if max_depth < 0:
        return "Error: max_depth must be >= 0."
    if not path.is_dir():
        return "error: not a directory"

    lines = [f"{path}/"]
    lines.extend(_tree_lines(path, "", 1, max_depth))

    total = len(lines)
    if total > MAX_TREE_LINES:
        omitted = total - MAX_TREE_LINES
        lines = lines[:MAX_TREE_LINES]
        lines.append(
            f"... ({omitted} more line{'s' if omitted != 1 else ''} omitted — "
            f"max {MAX_TREE_LINES} lines shown; use a smaller max_depth or directory)"
        )
    return "\n".join(lines)
