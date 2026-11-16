from returns.result import Failure

from bond.fs_access import AccessMode
from bond.tools import tool


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
    grant = context.request_fs_access(file_path, AccessMode.WRITE)
    if isinstance(grant, Failure):
        return grant.failure()
    authorized = grant.unwrap()
    path = authorized.path
    if not authorized.exists() and not authorized.is_symlink():
        return "error: file does not exist"
    if authorized.is_dir():
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

    unlink_res = authorized.unlink()
    if isinstance(unlink_res, Failure):
        return unlink_res.failure()
    return f"Removed file {path}"
