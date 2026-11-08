import json
from abc import ABC, abstractmethod
from typing import Any, Collection

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


def prefix_tool_description(description: Tool, prefix: str) -> Tool:
    """Return a copy of a tool description with ``prefix`` prepended to the tool name."""
    return description.model_copy(
        update={
            "function": description.function.model_copy(
                update={"name": prefix + description.function.name}
            )
        }
    )


class PrefixedToolset(Toolset):
    """Wraps a toolset and exposes it under a namespaced name.

    The toolset's name and every tool's ``function.name`` get ``prefix``
    prepended (e.g. ``sk:pdf:``), so skill-provided tools can never collide
    with persona or builtin tools. Execution is routed through the original
    (unprefixed) BondTools.
    """

    def __init__(self, toolset: Toolset, prefix: str):
        super().__init__(prefix + toolset.name)
        self._toolset = toolset
        self._prefix = prefix

    def activate(self) -> "ActivePrefixedToolset":
        active = self._toolset.activate()
        tools = [
            BondTool(
                tool.base_fn, prefix_tool_description(tool.description, self._prefix)
            )
            for tool in active.tools
        ]
        return ActivePrefixedToolset(tools, active)


class ActivePrefixedToolset(ActiveToolset):
    def __init__(self, tools: list[BondTool], wrapped: ActiveToolset):
        super().__init__(tools)
        self._wrapped = wrapped

    def release(self):
        self._wrapped.release()


class Toolbox:
    def __init__(self, toolsets: Collection[Toolset]):
        self._toolsets = {toolset.name: toolset for toolset in toolsets}
        self._active_toolsets: dict[str, ActiveToolset] = {
            toolset.name: toolset.activate() for toolset in toolsets
        }
        self._tool_toolset_map: dict[str, str] = {}
        self._all_tool_descriptions: list[Tool] = []

        tool_names: set[str] = set()
        for toolset_name, toolset in self._active_toolsets.items():
            for tool_description in toolset.tool_descriptions:
                if (tool_name := tool_description.function.name) in tool_names:
                    raise ValueError(f"Duplicate tool name in toolbox: {tool_name}")
                tool_names.add(tool_name)
                self._tool_toolset_map[tool_name] = toolset_name
                self._all_tool_descriptions.append(tool_description)

    def add_toolset(self, toolset: Toolset) -> ActiveToolset:
        if toolset.name in self._toolsets:
            raise ValueError("Duplicate toolset name")
        active_toolset: ActiveToolset = toolset.activate()
        for tool in active_toolset.tools:
            if (
                toolset_name := tool.description.function.name
            ) in self._tool_toolset_map:
                raise ValueError(f"Duplicate tool name: {toolset_name}")
        for tool in active_toolset.tools:
            self._tool_toolset_map[tool.description.function.name] = toolset.name
            self._all_tool_descriptions.append(tool.description)
        self._toolsets[toolset.name] = toolset
        self._active_toolsets[toolset.name] = active_toolset
        return active_toolset

    def remove_toolset(self, name: str):
        if name not in self._toolsets:
            return
        active_toolset = self._active_toolsets[name]
        for tool in active_toolset.tools:
            del self._tool_toolset_map[tool.description.function.name]
            self._all_tool_descriptions.remove(tool.description)
        active_toolset.release()
        del self._toolsets[name]
        del self._active_toolsets[name]

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

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._tool_toolset_map

    @property
    def tool_descriptions(self) -> list[Tool]:
        return list(self._all_tool_descriptions)

    @property
    def toolset_names(self) -> list[str]:
        return list(self._toolsets.keys())

    @property
    def toolsets(self) -> list[Toolset]:
        return list(self._toolsets.values())

    def _find_tool(self, name: str) -> BondTool | None:
        if (toolset_name := self._tool_toolset_map.get(name)) is None:
            return None
        if (active_toolset := self._active_toolsets.get(toolset_name)) is None:
            active_toolset = self._toolsets[toolset_name].activate()
            self._active_toolsets[toolset_name] = active_toolset
        if (tool := active_toolset.get_tool(name)) is None:
            raise RuntimeError(f"Could not find tool in toolset: {name}")
        return tool
