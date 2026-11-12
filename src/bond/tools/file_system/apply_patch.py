import re

from bond.tools import tool
from bond.tools.file_system.util import (
    check_write_access,
    fuzzy_find_aider_patch_blocks,
)

_BLOCK_RE = re.compile(
    r"(?:(?P<file>[^\n]+)\n)?<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
    re.DOTALL,
)

CONTEXT_LINES = 3
MAX_SNIPPET_CHANGED_LINES = 20


def _format_change_snippet(new_text: str, start_line: int, n_changed: int) -> list[str]:
    """Format the changed region of `new_text` with context lines around it.

    `start_line` is the 0-based index of the first changed line in `new_text`
    and `n_changed` the number of lines the replacement occupies (0 for a
    deletion). Changed lines are prefixed with ">", context lines with " ".
    """
    lines = new_text.splitlines()
    window_start = max(0, start_line - CONTEXT_LINES)
    window_end = min(len(lines), start_line + n_changed + CONTEXT_LINES)
    width = len(str(max(window_end, 1)))
    snippet: list[str] = []
    i = window_start
    while i < window_end:
        if start_line <= i < start_line + n_changed:
            if i - start_line >= MAX_SNIPPET_CHANGED_LINES:
                remaining = n_changed - MAX_SNIPPET_CHANGED_LINES
                snippet.append(f"  ... ({remaining} more changed lines)")
                i = start_line + n_changed  # skip to the trailing context
                continue
            marker = ">"
        else:
            marker = " "
        snippet.append(f"{marker} {i + 1:>{width}}: {lines[i]}")
        i += 1
    return snippet


@tool.tool(
    name="apply_patch",
    description="""
    Apply Aider-style SEARCH/REPLACE patches.
    The user has to manually accept the changes unless specific conditions are met.
    Patch blocks must begin with a filename line.
    All file paths have to be located inside the current working directory.
    Relative paths will be interpreted as relative to the cwd.
    `.bond` and `.git` directories are read-only: patching files inside them is not allowed.
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
        - For every successfully applied block, the result contains the
          changed region of the file with a few lines of context before and
          after (changed lines are marked with ">"), so you can verify that
          the patch landed at the right position without re-reading the file.
    """,
    parameters={
        "patch": tool.FunctionParameter(
            type="string", description="One or more SEARCH/REPLACE blocks."
        )
    },
    required=["patch"],
)
def apply_patch(context: tool.ToolCallContext, patch: str) -> str:
    skip_confirmation = (
        context.cwd is not None
        and (context.cwd / ".git").exists()
        and (context.cwd / ".git").is_dir()
    )

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

        try:
            path = context.resolve_path(file)
        except ValueError as e:
            results.append(f"Block {idx}: failed, {e}")
            continue
        if path is None:
            results.append(
                f"Block {idx}: failed, tool access to the filesystem is currently disabled."
            )
            continue
        if not path.exists():
            results.append(f"Block {idx}: failed, file does not exist.")
            continue

        has_access, why_not = check_write_access(context, path)
        if not has_access:
            results.append(f"Block {idx}: failed, {why_not}")
            continue

        text = path.read_text()
        replace_lines = replace.splitlines()
        n_changed = len(replace_lines)
        if search in text:
            new_text = text.replace(search, replace, 1)
            start_line = text[: text.index(search)].count("\n")
        else:
            span = fuzzy_find_aider_patch_blocks(text, search)
            if span is None:
                results.append(f"Block {idx}: failed, search term not found")
                continue

            lines = text.splitlines()
            start, end = span
            new_lines = lines[:start] + replace_lines + lines[end:]
            new_text = "\n".join(new_lines)
            start_line = start
        path.write_text(new_text)

        if n_changed > 0:
            header = (
                f"Block {idx}: success — {file} "
                f"(changed lines {start_line + 1}-{start_line + n_changed})"
            )
        else:
            header = f"Block {idx}: success — {file} (deletion at line {start_line + 1})"
        results.append(header)
        results.extend(_format_change_snippet(new_text, start_line, n_changed))
        modified_files.add(file)

    if len(modified_files) > 0:
        results.append(f"Modified files: {modified_files}")
    else:
        results.append(
            f"No files were modified. Make sure to use the correct patch syntax."
        )
    return "\n".join(results)
