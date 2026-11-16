import re

from returns.result import Failure

from bond.fs_access import AccessMode
from bond.tools import tool


@tool.tool(
    name="create_file",
    description="""
    Create a new file at the specified path with the given content.
    You are only expected to access files inside the current working directory.
    When creating files outside of the current working directory, the user has to manually grant access.
    Directories that do not exist yet will be created automatically.
    `.bond` and `.git` directories are read-only: creating files inside them is not allowed.
    """,
    parameters={
        "file_path": tool.FunctionParameter(
            type="string", description="The path where the new file should be created"
        ),
        "content": tool.FunctionParameter(
            type="string", description="The content of the new file"
        ),
    },
    required=["file_path", "content"],
)
def create_file(context: tool.ToolCallContext, file_path: str, content: str) -> str:
    grant = context.request_fs_access(file_path, AccessMode.WRITE)
    if isinstance(grant, Failure):
        return grant.failure()
    authorized = grant.unwrap()
    if authorized.exists():
        return "error: file already exists"
    write_res = authorized.write_text(content)
    if isinstance(write_res, Failure):
        return write_res.failure()
    return f"Created file at {authorized.path}"
