from bond.tools import tool
from bond.tools.file_system.util import check_write_access


@tool.tool(
    name="remove_file",
    description="""
    Remove (delete) a single file at the specified path.
    You are only expected to access files inside the current working directory.
    When removing files outside of the current working directory, the user has to manually grant access.
    Only files can be removed — directories are refused.
    A symbolic link is removed as a link; its target is never touched.
    `.bond` and `.git` directories are read-only: removing files inside them is not allowed.
    In a git repository the removal is not confirmed (tracked files can be restored with git);
    otherwise the user is asked for confirmation in interactive mode.
    """,
    parameters={
        "file_path": tool.FunctionParameter(
            type="string", description="The path of the file to remove"
        ),
    },
    required=["file_path"],
)
def remove_file(context: tool.ToolCallContext, file_path: str) -> str:
    try:
        path = context.resolve_path(file_path)
    except ValueError as e:
        return f"Error: {e}"
    if path is None:
        return "Error: Tool access to the filesystem is currently disabled."
    has_access, why_not = check_write_access(context, path)
    if not has_access:
        return why_not
    if not path.exists() and not path.is_symlink():
        return "error: file does not exist"
    if path.is_dir():
        return "error: path is a directory, only files can be removed"

    skip_confirmation = (
        context.cwd is not None
        and (context.cwd / ".git").exists()
        and (context.cwd / ".git").is_dir()
    )
    if not skip_confirmation and not context.ask_confirmation(
        f"Bond wants to remove the file {path}.\nRemove file?"
    ):
        return "Removal cancelled by user."

    try:
        path.unlink()
        return f"Removed file {path}"
    except Exception as e:
        return f"Error removing file: {str(e)}"
