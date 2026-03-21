import os
from pathlib import Path

from bond.tools import tool


def _check_access(env: tool.ToolEnvironment, cwd: Path, path: Path):
    if path.is_relative_to(cwd):
        return True, ""
    if env.is_interactive() is None:
        return (
            False,
            f"Permission denied, this tool is not run in interactive mode. Cannot access files outside of '{cwd}'",
        )
    if not env.ask_confirmation(
        f"Bond wants to access the contents of {path}, which lies outside of the current working directory.\nDo you want to grant access?"
    ):
        return False, "Permission denied, the user has declined your request."
    return True, ""


def create_file(file_path: str, content: str) -> str:
    """
    Create a new file at the specified path with the given content.
    You are only expected to access files inside the current working directory.
    When creating files outside of the current working directory, the user has to manually grant access.

    Args:
        file_path (str): The path where the new file should be created.
        content (str): The contents of the new file.

    Returns:
        None
    """
    env = tool.get_tool_environment()
    current_directory = Path(os.getcwd()).absolute()
    path = current_directory / Path(file_path)
    has_access, why_not = _check_access(env, current_directory, path)
    if not has_access:
        return why_not
    if path.exists():
        return "error: file already exists"
    path.write_text(content)
    return f"Created file at {path}"


def read_file(file_path: str, lines: int = 0) -> str:
    """
    Read the contents of the specified file.
    You are only expected to access files inside the current working directory.
    When accessing files outside of the current working directory, the user has to manually grant access.
    You can specify how many lines from the top you want to read.

    Args:
        file_path (str): The path of the file to read.
        lines (int): How many lines to read. Read all lines, if lines = 0

    Returns:
        str: The contents of the file
    """
    env = tool.get_tool_environment()
    current_directory = Path(os.getcwd()).absolute()
    path = current_directory / Path(file_path)
    has_access, why_not = _check_access(env, current_directory, path)
    if not has_access:
        return why_not
    if not path.is_file():
        return "error: not a file"
    content = path.read_text()
    if lines <= 0:
        return content
    return content[:lines]


def list_directory(dir_path: str) -> str:
    """
    List the contents of the specified directory.
    You are only expected to access locations inside the current working directory.
    When accessing paths outside of the current working directory, the user has to manually grant access.

    Args:
        dir_path (str): The path to the directory to list.

    Returns:
        str: The contents of the directory
    """
    env = tool.get_tool_environment()
    current_directory = Path(os.getcwd()).absolute()
    path = current_directory / Path(dir_path)
    has_access, why_not = _check_access(env, current_directory, path)
    if not has_access:
        return why_not
    if not path.is_dir():
        return "error: not a directory"
    children = current_directory.iterdir()
    results = [f"{child}: {'dir' if child.is_dir() else 'file'}" for child in children]
    return f"Contents of {path}:\n" + "\n".join(results)
