import difflib
import re
from pathlib import Path

from bond.tools import tool

_BLOCK_RE = re.compile(
    r"(?:(?P<file>[^\n]+)\n)?<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
    re.DOTALL,
)


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
def create_file(file_path: str, content: str) -> str:
    env = tool.get_tool_environment()
    work_dir = env.get_work_dir()
    if work_dir is None:
        return "Error: Tool access to the filesystem is currently disabled."
    current_directory = work_dir.absolute()
    path = current_directory / Path(file_path)
    has_access, why_not = _check_access(env, path)
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


@tool.tool(
    name="read_file",
    description="""
    Read the contents of the specified file.
    You are only expected to access files inside the current working directory.
    When accessing files outside of the current working directory, the user has to manually grant access.
    You can specify how many lines from the top you want to read.
""",
    parameters={
        "file_path": tool.FunctionParameter(
            type="string", description="The path of the file to read."
        ),
        "content": tool.FunctionParameter(
            type="integer",
            description="How many lines to read. Read all lines, if lines = 0. Default value is 0.",
        ),
    },
    required=["file_path"],
)
def read_file(file_path: str, lines: int = 0) -> str:
    env = tool.get_tool_environment()
    work_dir = env.get_work_dir()
    if work_dir is None:
        return "Error: Tool access to the file system is currently disabled."
    current_directory = work_dir.absolute()
    path = current_directory / Path(file_path)
    has_access, why_not = _check_access(env, path)
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
    work_dir = env.get_work_dir()
    if work_dir is None:
        return "Error: Tool access to the filesystem is currently disabled."
    current_directory = work_dir.absolute()
    path = current_directory / Path(dir_path)
    has_access, why_not = _check_access(env, path)
    if not has_access:
        return why_not
    if not path.is_dir():
        return "error: not a directory"
    children = path.iterdir()
    results = [f"{child}: {'dir' if child.is_dir() else 'file'}" for child in children]
    return f"Contents of {path}:\n" + "\n".join(results)


def get_cwd() -> str:
    """
    Retrieves the current working directory (cwd)
    that is used for all file related tool operations.
    """

    env = tool.get_tool_environment()
    work_dir = env.get_work_dir()
    if work_dir is None:
        return "error: file operations are not available at the moment"
    return work_dir.as_posix()


def apply_patch(patch: str) -> str:
    """
    Apply Aider-style SEARCH/REPLACE patches.
    The user has to manually accept the changes unless specific conditions are met.
    Patch blocks must begin with a filename line.
    All file paths have to be located inside the current working directory.
    Relative paths will be interpreted as relative to the cwd.
    Keep the search blocks unique, but skip long prefixes that should remain unchanged.

    Example block:

        path/to/file.py
        <<<<<<< SEARCH
        old code
        =======
        new code
        >>>>>>> REPLACE

    You can chain as many blocks in one request as you want.
    Prefer fewer requests with multiple blocks over many requests
    with only one or two blocks.

    Args:
        patch (str): One or more SEARCH/REPLACE blocks.

    Returns:
        Dictionary describing results:
        {
            "applied": int,
            "failed": int,
            "files_modified": [paths]
        }

    Behavior:
        - SEARCH blocks should contain the current code.
        - Replacement occurs once per block.
        - If exact match fails, fuzzy matching is attempted.
    """

    env = tool.get_tool_environment()
    work_dir = env.get_work_dir()
    if work_dir is None:
        return "error: file modification is not available at the moment"

    git_dir = work_dir / ".git"
    skip_confirmation = git_dir.exists() and git_dir.is_dir()

    if not skip_confirmation and not env.ask_confirmation(
        f"Bond wants to apply the following changes:\n\n{patch}\nMake changes?"
    ):
        return "Patching cancelled by user."

    results: list[str] = []
    modified_files: set[str] = set()

    patch_blocks = list(_BLOCK_RE.finditer(patch))
    if len(patch_blocks) == 0:
        return """Error: patch format. Could not find any valid patch blocks. Please stick to this format:
        path/to/file.py
        <<<<<<< SEARCH
        old code
        =======
        new code
        >>>>>>> REPLACE
        """

    for idx, m in enumerate(patch_blocks):

        file = m.group("file")
        search = m.group("search")
        replace = m.group("replace")

        if not file:
            results.append(f"Block {idx}: failed, no file specified.")
            continue

        path = work_dir / file
        if not path.exists():
            results.append(f"Block {idx}: failed, file does not exist.")
            continue

        if _path_is_in_git(path):
            results.append(
                f"Block {idx}: failed, file is inside .git folder (permission denied)"
            )
            continue

        text = path.read_text()
        if search in text:
            new_text = text.replace(search, replace, 1)
        else:
            span = _find_fuzzy_match(text, search)
            if span is None:
                results.append(f"Block {idx}: failed, search term not found")
                continue

            lines = text.splitlines()
            start, end = span
            new_lines = lines[:start] + replace.splitlines() + lines[end:]
            new_text = "\n".join(new_lines)
        path.write_text(new_text)

        results.append(f"Block {idx}: success")
        modified_files.add(file)

    results.append(f"Modified files: {modified_files}")
    return "\n".join(results)


def _normalize(text: str):
    """Normalize text for fuzzy comparison."""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _find_fuzzy_match(text: str, search: str):
    """
    Find best approximate match of search block in text.
    Returns (start_index, end_index) or None.
    """

    norm_search = _normalize(search)
    text_lines = text.splitlines()
    search_lines = search.splitlines()

    best_ratio = 0
    best_span = None

    for i in range(len(text_lines)):
        window = text_lines[i : i + len(search_lines)]
        if not window:
            continue

        candidate = "\n".join(window)
        ratio = difflib.SequenceMatcher(
            None, _normalize(candidate), norm_search
        ).ratio()

        if ratio > best_ratio:
            best_ratio = ratio
            best_span = (i, i + len(search_lines))

    if best_ratio > 0.85:
        return best_span

    return None


def _check_access(env: tool.ToolEnvironment, path: Path):
    work_dir = env.get_work_dir()
    if work_dir is None:
        return (
            False,
            "Permission denied, tool access to the filesystem is currently disabled.",
        )
    if path.is_relative_to(work_dir):
        return True, ""
    if not env.is_interactive():
        return (
            False,
            f"Permission denied, this tool is not run in interactive mode. Cannot access files outside of '{work_dir}'",
        )
    if not env.ask_confirmation(
        f"Bond wants to access the contents of {path}, which lies outside of the current working directory.\nDo you want to grant access?"
    ):
        return False, "Permission denied, the user has declined your request."
    return True, ""


def _path_is_in_git(path: Path) -> bool:
    for x in path.parts:
        if x == ".git":
            return True
    return False
