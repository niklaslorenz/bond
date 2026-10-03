import re
from pathlib import Path

from bond.tools import tool
from bond.tools.file_system.util import check_access
from bond.util import resolve_path


@tool.tool(
    name="create_file",
    description="""
    Create a new file at the specified path with the given content.
    You are only expected to access files inside the current working directory.
    When creating files outside of the current working directory, the user has to manually grant access.
    Directories that do not exist yet will be created automatically.
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
    if context.cwd is None:
        return "Error: Tool access to the filesystem is currently disabled."
    path = resolve_path(context.cwd, Path(file_path))
    has_access, why_not = check_access(context, path)
    if not has_access:
        return why_not
    if path.exists():
        return "error: file already exists"
    try:
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Created file at {path}"
    except Exception as e:
        return f"Error creating file: {str(e)}"
