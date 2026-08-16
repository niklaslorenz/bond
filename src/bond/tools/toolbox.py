import json
from typing import Any

from returns.result import Failure, Result, Success

from bond.tools.tool import BondTool, Tool

from . import logger

Toolset = list[BondTool]


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
