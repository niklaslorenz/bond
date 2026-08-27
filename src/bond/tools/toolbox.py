import json
from abc import ABC, abstractmethod
from typing import Any, List

from returns.result import Failure, Result, Success

from bond.tools.tool import BondTool, Tool, ToolCallContext

from . import logger


class Toolset(ABC):
    """Abstract base class for toolsets."""

    def __init__(self, name: str):
        self.name = name
        self._initialized = False

    @abstractmethod
    def initialize(self) -> List[BondTool]:
        """Initialize the toolset and return a list of BondTools."""
        pass

    def is_initialized(self) -> bool:
        """Check if the toolset is initialized."""
        return self._initialized

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources (e.g., close connections)."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, initialized={self._initialized})"


class PythonToolset(Toolset):
    """A toolset that holds a static list of Python-based BondTools."""

    def __init__(self, name: str, tools: List[BondTool]):
        super().__init__(name)
        self._tools = tools

    def initialize(self) -> List[BondTool]:
        """Return the static list of tools."""
        self._initialized = True
        return self._tools

    def cleanup(self) -> None:
        """No cleanup needed for static tools."""
        self._initialized = False


class Toolbox:
    tool_map: dict[str, BondTool]

    def __init__(self, tools: dict[str, BondTool] | list[BondTool] | set[BondTool]):
        self.tool_map = (
            {t.description.function.name: t for t in tools}
            if isinstance(tools, list) or isinstance(tools, set)
            else dict(tools)
        )

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolCallContext,
    ) -> Result[str, str]:
        if tool_name not in self.tool_map:
            logger.warning(f"Tried to call unknown tool: {tool_name}")
            return Failure("Invalid tool name")
        try:
            logger.debug(f"Calling tool {tool_name} with arguments '{arguments}'")
            result = self.tool_map[tool_name](context, **arguments)
            if result is None:
                return Success("Success (no output)")
            if isinstance(result, str):
                return Success(result)
            return Success(json.dumps(result))
        except Exception as e:
            return Failure(f"An error occured during tool call ({type(e)}): {e}")

    def get_tool_descriptions(self) -> list[Tool]:
        return [t.description for t in self.tool_map.values()]
