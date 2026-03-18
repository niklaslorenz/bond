import json
from typing import Any, Callable

from returns.result import Failure, Result, Success
from smolagents.tools import get_json_schema

from . import logger

Tool = Callable[..., str | list[str] | dict[str, Any] | list[dict[str, Any]]]


def _build_tool_description(fn: Tool) -> dict:
    raw = get_json_schema(fn)
    if "return" in raw["function"]:
        raw["function"].pop("return")
    return raw


class Toolbox:
    def __init__(self, tools: list[Tool]):
        self.tools = [(_build_tool_description(tool), tool) for tool in tools]
        self.tool_map = {desc["function"]["name"]: tool for desc, tool in self.tools}
        self.tool_descriptions = [desc for desc, _ in self.tools]

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
