from pathlib import Path

from bond.tools import tool
from bond.tools.file_system.util import check_access
from bond.util import resolve_path


@tool.tool(
    name="list_directory",
    description="""
    List the contents of the specified directory.
    You are only expected to access locations inside the current working directory.
    When accessing paths outside of the current working directory, the user has to manually grant access.

    Args:
        dir_path (str): The path to the directory to list.

    Returns:
        str: The contents of the directory
    """,
    parameters={
        "dir_path": tool.FunctionParameter(
            type="string", description="directory path (absolute or relative to cwd)"
        )
    },
    required=["dir_path"],
)
def list_directory(context: tool.ToolCallContext, dir_path: str) -> str:
    if context.cwd is None:
        return "Error: Tool access to the filesystem is currently disabled."
    path = resolve_path(context.cwd, Path(dir_path))
    has_access, why_not = check_access(context, path)
    if not has_access:
        return why_not
    if not path.is_dir():
        return "error: not a directory"
    children = path.iterdir()
    results = [f"{child}: {'dir' if child.is_dir() else 'file'}" for child in children]
    return f"Contents of {path}:\n" + "\n".join(results)
