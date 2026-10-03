from pathlib import Path

from bond.tools import tool


@tool.tool(
    name="get_cwd",
    description="""
    Retrieves the current working directory (cwd)
    that is used for all file related tool operations.
    """,
    parameters={},
)
def get_cwd(context: tool.ToolCallContext) -> str:
    work_dir = context.cwd
    if work_dir is None:
        return "error: file operations are not available at the moment"
    return work_dir.absolute().expanduser().as_posix()
