import json
from typing import Any

from returns.result import Failure, Result, Success

from bond.tools.fs_tools import (
    apply_patch,
    create_file,
    get_cwd,
    list_directory,
    read_file,
)
from bond.tools.shell_tools import run_shell_commands
from bond.tools.stream_tools import write_to_output
from bond.tools.tool import BondTool, Tool
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web

from . import logger

Toolset = list[BondTool]

_all_toolsets: dict[str, Toolset] = {
    "web": [search_the_web, access_web],
    "file": [list_directory, create_file, read_file, apply_patch, get_cwd],
    "shell": [run_shell_commands],
    "write": [write_to_output],
}


def register_toolset(name: str, toolset: Toolset):
    if name in _all_toolsets:
        raise ValueError(f"Duplicate Toolset Name: {name}")
    _all_toolsets[name] = toolset


def get_toolset(toolset: str) -> Toolset | None:
    return _all_toolsets.get(toolset)


def get_toolsets(toolsets: list[str]) -> dict[str, Toolset]:
    selected_toolsets = {}
    for name in toolsets:
        if name not in _all_toolsets:
            logger.error(f"Invalid Toolset name '{name}'")
        selected_toolsets[name] = _all_toolsets[name]
    return selected_toolsets

class Toolbox:
    tool_map: dict[str, BondTool]

    def __init__(self, tools: dict[str, BondTool] | list[BondTool] | set[BondTool]):
        self.tool_map = (
            {t.description.function.name: t for t in tools}
            if isinstance(tools, list) or isinstance(tools, set)
            else dict(tools)
        )

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Result[str, str]:
        if tool_name not in self.tool_map:
            logger.warning(f"Tried to call unknown tool: {tool_name}")
            return Failure("Invalid tool name")
        try:
            logger.debug(f"Calling tool {tool_name} with arguments '{arguments}'")
            result = self.tool_map[tool_name](**arguments)
            if result is None:
                return Success("Success (no output)")
            if isinstance(result, str):
                return Success(result)
            return Success(json.dumps(result))
        except Exception as e:
            return Failure(f"An error occured during tool call ({type(e)}): {e}")

    def get_tool_descriptions(self) -> list[Tool]:
        return [t.description for t in self.tool_map.values()]

    @classmethod
    def from_toolset_names(cls, toolset_names: list[str]) -> "Toolbox":
        return Toolbox({t for ts in get_toolsets(toolset_names).values() for t in ts})
