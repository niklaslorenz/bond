from bond.tools.fs_tools import create_file, list_directory, read_file
from bond.tools.shell import run_shell_commands
from bond.tools.tool import Tool, Toolset
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web

_all_toolsets: dict[str, Toolset] = {
    "web-tools": [search_the_web, access_web],
    "fs-tools": [list_directory, create_file, read_file],
    "shell": [run_shell_commands],
}


def get_toolsets(toolsets: list[str]) -> dict[str, Toolset]:
    return {k: v.copy() for k, v in _all_toolsets.items() if k in toolsets}
