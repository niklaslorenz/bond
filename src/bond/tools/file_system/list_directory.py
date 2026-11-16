from returns.result import Failure

from bond.fs_access import AccessMode
from bond.tools import tool


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
    grant = context.request_fs_access(dir_path, AccessMode.READ)
    if isinstance(grant, Failure):
        return grant.failure()
    authorized = grant.unwrap()
    if not authorized.is_dir():
        return "error: not a directory"
    children_res = authorized.iterdir()
    if isinstance(children_res, Failure):
        return children_res.failure()
    results = [
        f"{child.path}: {'dir' if child.is_dir() else 'file'}"
        for child in children_res.unwrap()
    ]
    return f"Contents of {authorized.path}:\n" + "\n".join(results)
