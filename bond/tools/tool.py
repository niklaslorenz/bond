import json
from typing import Any, Callable

from returns.result import Failure, Result, Success

from . import logger

Tool = Callable[..., str | list[str] | dict[str, Any] | list[dict[str, Any]]]


class Toolbox:

    def __init__(self, tools: dict[str, tuple[Tool, dict[str, Any]]]):
        self.tool_map = {name: tool for name, (tool, _) in tools.items()}
        self.tool_descriptions = [desc for (_, desc) in tools.values()]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Result[str, str]:
        if tool_name not in self.tool_map:
            logger.debug(f"Tried to call invalid tool: {tool_name}")
            return Failure("Invalid tool name")
        try:
            logger.debug(f"Calling tool {tool_name} with arguments '{arguments}'")
            result = self.tool_map[tool_name](**arguments)
            if isinstance(result, str):
                return Success(result)
            return Success(json.dumps(result))
        except Exception as e:
            return Failure(f"An error occured during tool call ({type(e)}): {e}")

    def get_tool_descriptions(self):
        return self.tool_descriptions
