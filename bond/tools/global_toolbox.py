from bond.tools.fs_tools import create_file, list_directory, read_file
from bond.tools.shell import run_shell_commands
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web


def build_global_toolsets():
    return {
        "web-tools": [search_the_web, access_web],
        "fs-tools": [list_directory, create_file, read_file],
        "shell": [run_shell_commands],
    }
