"""Recursive directory tree listing tool."""

from returns.result import Failure, Success

from bond.fs_access import AccessMode, AuthorizedPath
from bond.tools import tool

# Hard cap on displayed lines; anything beyond is omitted with a notice.
MAX_TREE_LINES = 200

DEFAULT_MAX_DEPTH = 3


def _tree_lines(
    node: AuthorizedPath, prefix: str, depth: int, max_depth: int
) -> list[str]:
    """Build the tree lines for the entries of ``node`` at the given depth.

    Symlinked directories are shown as ``name -> target`` and never recursed
    into, so symlink cycles cannot blow up the listing.
    """
    if depth > max_depth:
        return []
    children_res = node.iterdir()
    if isinstance(children_res, Failure):
        return [f"{prefix}[error: {children_res.failure()}]"]
    entries = sorted(
        children_res.unwrap(),
        key=lambda c: (not c.is_dir(follow_symlinks=False), c.path.name.lower()),
    )

    lines: list[str] = []
    for i, entry in enumerate(entries):
        last = i == len(entries) - 1
        connector = "└── " if last else "├── "
        if entry.is_symlink():
            target_res = entry.readlink()
            target = target_res.unwrap() if isinstance(target_res, Success) else "?"
            lines.append(f"{prefix}{connector}{entry.path.name} -> {target}")
            continue
        if entry.is_dir(follow_symlinks=False):
            lines.append(f"{prefix}{connector}{entry.path.name}/")
            extension = "    " if last else "│   "
            lines.extend(_tree_lines(entry, prefix + extension, depth + 1, max_depth))
        else:
            lines.append(f"{prefix}{connector}{entry.path.name}")
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
    grant = context.request_fs_access(dir_path, AccessMode.READ, recursive=True)
    if isinstance(grant, Failure):
        return grant.failure()
    authorized = grant.unwrap()
    if max_depth < 0:
        return "Error: max_depth must be >= 0."
    if not authorized.is_dir():
        return "error: not a directory"

    lines = [f"{authorized.path}/"]
    lines.extend(_tree_lines(authorized, "", 1, max_depth))

    total = len(lines)
    if total > MAX_TREE_LINES:
        omitted = total - MAX_TREE_LINES
        lines = lines[:MAX_TREE_LINES]
        lines.append(
            f"... ({omitted} more line{'s' if omitted != 1 else ''} omitted — "
            f"max {MAX_TREE_LINES} lines shown; use a smaller max_depth or directory)"
        )
    return "\n".join(lines)
