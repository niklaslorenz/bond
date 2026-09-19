import json
from abc import ABC, abstractmethod
from typing import Any, Collection, List, Self

from returns.result import Failure, Result, Success

from bond.tools.tool import BondTool, Tool, ToolCallContext

from . import logger


class ActiveToolset:
    def __init__(self, tools: list[BondTool]):
        self._tools = tools
        self._tool_map = {tool.description.function.name: tool for tool in tools}

    @property
    def tools(self) -> list[BondTool]:
        return list(self._tools)

    @property
    def tool_descriptions(self) -> list[Tool]:
        return [tool.description for tool in self._tools]

    def get_tool(self, name: str) -> BondTool | None:
        return self._tool_map.get(name)

    def release(self):
        pass


class Toolset[ActiveToolsetType: ActiveToolset](ABC):
    """Abstract base class for toolsets."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self):
        return self._name

    @abstractmethod
    def activate(self) -> ActiveToolsetType: ...

    @property
    @abstractmethod
    def tool_descriptions(self) -> list[Tool]: ...

    @abstractmethod
    def get_tool_description(self, name: str) -> Tool | None: ...


class PythonToolset(Toolset):
    """A toolset that holds a static list of Python-based BondTools."""

    def __init__(self, name: str, tools: list[BondTool]):
        super().__init__(name)
        self._tools = tools
        self._tool_map = {tool.description.function.name: tool for tool in tools}

    def activate(self) -> ActiveToolset:
        return ActiveToolset(self._tools)

    @property
    def tool_descriptions(self) -> list[Tool]:
        return [tool.description for tool in self._tools]

    def get_tool_description(self, name: str) -> Tool | None:
        if (tool := self._tool_map.get(name)) is not None:
            return tool.description
        return None


class Toolbox:
    def __init__(self, toolsets: Collection[Toolset]):
        self._toolsets = {toolset.name: toolset for toolset in toolsets}
        self._active_toolsets: dict[str, ActiveToolset] = {}
        self._tool_toolset_map: dict[str, str] = {}
        self._all_tool_descriptions: list[Tool] = []

        tool_names: set[str] = set()
        for toolset in toolsets:
            for tool_description in toolset.tool_descriptions:
                if (tool_name := tool_description.function.name) in tool_names:
                    raise ValueError(f"Duplicate tool name in toolbox: {tool_name}")
                tool_names.add(tool_name)
                self._tool_toolset_map[tool_name] = toolset.name
                self._all_tool_descriptions.append(tool_description)

    def release(self):
        for active_toolset in self._active_toolsets.values():
            active_toolset.release()
        self._active_toolsets.clear()

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolCallContext,
    ) -> Result[str, str]:
        if (tool := self._find_tool(tool_name)) is None:
            logger.warning(f"Tried to call unknown tool: {tool_name}")
            return Failure("Invalid tool name")
        try:
            logger.debug(f"Calling tool {tool_name} with arguments '{arguments}'")
            result = tool(context, **arguments)
            if result is None:
                return Success("Success (no output)")
            if isinstance(result, str):
                return Success(result)
            return Success(json.dumps(result))
        except Exception as e:
            return Failure(f"An error occured during tool call ({type(e)}): {e}")

    @property
    def tool_descriptions(self) -> list[Tool]:
        return list(self._all_tool_descriptions)

    def _find_tool(self, name: str) -> BondTool | None:
        if (toolset_name := self._tool_toolset_map.get(name)) is None:
            return None
        if (active_toolset := self._active_toolsets.get(toolset_name)) is None:
            active_toolset = self._toolsets[toolset_name].activate()
            self._active_toolsets[toolset_name] = active_toolset
        if (tool := active_toolset.get_tool(name)) is None:
            raise RuntimeError(f"Could not find tool in toolset: {name}")
        return tool
