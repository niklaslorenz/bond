from bond.tools.fs_tools import (apply_patch, create_file, get_cwd,
                                 list_directory, read_file)
from bond.tools.shell import run_shell_commands
from bond.tools.stream_tools import write_to_output
from bond.tools.tool import Toolset
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web

_all_toolsets: dict[str, Toolset] = {
    "web-tools": [search_the_web, access_web],
    "fs-tools": [list_directory, create_file, read_file, apply_patch, get_cwd],
    "shell": [run_shell_commands],
    "write": [write_to_output],
}


def get_toolsets(toolsets: list[str]) -> dict[str, Toolset]:
    selected_toolsets = {}
    for name in toolsets:
        if name not in _all_toolsets:
            raise ValueError(f"Invalid Toolset name '{name}'")
        selected_toolsets[name] = _all_toolsets[name]
    return selected_toolsets
