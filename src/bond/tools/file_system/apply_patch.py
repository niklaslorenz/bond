import re
from pathlib import Path

from bond.tools import tool
from bond.tools.file_system.util import (
    check_access,
    fuzzy_find_aider_patch_blocks,
    path_is_in_git,
)
from bond.util import resolve_path

_BLOCK_RE = re.compile(
    r"(?:(?P<file>[^\n]+)\n)?<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
    re.DOTALL,
)


@tool.tool(
    name="apply_patch",
    description="""
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
    
    Behavior:
        - SEARCH blocks should contain the current code.
        - Replacement occurs once per block.
        - If exact match fails, fuzzy matching is attempted.
    """,
    parameters={
        "patch": tool.FunctionParameter(
            type="string", description="One or more SEARCH/REPLACE blocks."
        )
    },
    required=["patch"],
)
def apply_patch(context: tool.ToolCallContext, patch: str) -> str:
    if context.cwd is None:
        return "error: file modification is not available at the moment"

    git_dir = context.cwd / ".git"
    skip_confirmation = git_dir.exists() and git_dir.is_dir()

    if not skip_confirmation and not context.ask_confirmation(
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

        path = resolve_path(context.cwd, Path(file))
        if not path.exists():
            results.append(f"Block {idx}: failed, file does not exist.")
            continue

        if path_is_in_git(path):
            results.append(
                f"Block {idx}: failed, file is inside .git folder (permission denied)"
            )
            continue

        text = path.read_text()
        if search in text:
            new_text = text.replace(search, replace, 1)
        else:
            span = fuzzy_find_aider_patch_blocks(text, search)
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

    if len(modified_files) > 0:
        results.append(f"Modified files: {modified_files}")
    else:
        results.append(
            f"No files were modified. Make sure to use the correct patch syntax."
        )
    return "\n".join(results)
