import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import local
from typing import Any, Callable, Generic, Literal, ParamSpec, Protocol, TextIO

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from . import logger

P = ParamSpec("P")

ToolReturnType = str | list[str] | dict[str, Any] | list[dict[str, Any]]
ToolFn = Callable[..., ToolReturnType]
Toolset = list[ToolFn]


class FunctionParameter(BaseModel):
    type: Literal["string", "number", "integer", "boolean", "array", "object"]
    description: str


class FunctionParameters(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, FunctionParameter]
    required: list[str] = []


class Function(BaseModel):
    name: str
    description: str = ""
    parameters: FunctionParameters
    strict: bool = False


class Tool(BaseModel):
    type: Literal["function"] = "function"
    function: Function


class BondTool(Generic[P]):
    base_fn: Callable[P, ToolReturnType]
    tool: Tool

    def __init__(self, base_fn: Callable[P, ToolReturnType], tool: Tool):
        self.base_fn = base_fn
        self.tool = tool

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> ToolReturnType:
        return self.base_fn(*args, **kwargs)


def tool(
    *,
    name: str,
    description: str,
    parameters: dict[str, FunctionParameter],
    required: list[str] = [],
    strict: bool = False,
):
    def build_tool(base_fn: Callable[P, ToolReturnType]) -> BondTool[P]:
        tool = BondTool(
            base_fn,
            Tool(
                function=Function(
                    name=name,
                    description=description,
                    parameters=FunctionParameters(
                        properties=parameters, required=required
                    ),
                    strict=strict,
                )
            ),
        )
        tool.__doc__ = description
        return tool

    return build_tool


_tool_locals = local()


@dataclass
class BidirectionalTextIO:
    text_in: TextIO
    text_out: TextIO


class ToolEnvironment(Protocol):
    def ask_confirmation(self, prompt: str) -> bool: ...

    def is_interactive(self) -> bool: ...

    def get_work_dir(self) -> Path | None: ...

    def supports_stdout(self) -> bool: ...

    def stdout(self) -> TextIO | None: ...

    def log_out(self) -> TextIO | None: ...

    def log_err(self) -> TextIO | None: ...


def get_tool_environment() -> ToolEnvironment:
    global _tool_locals
    if not hasattr(_tool_locals, "env") or _tool_locals.env is None:
        raise RuntimeError("No tool environment")
    return _tool_locals.env


@contextmanager
def activate_environment(env: ToolEnvironment):
    global _tool_locals
    if not hasattr(_tool_locals, "env"):
        _tool_locals.env = None
    old_env = _tool_locals.env
    _tool_locals.env = env
    try:
        yield
    finally:
        _tool_locals.env = old_env


class Toolbox:
    tool_map: dict[str, ToolFn]
    tool_descriptions: list[Tool]

    def __init__(self, tools: dict[str, tuple[ToolFn, Tool]]):
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

    def get_tool_descriptions(self) -> list[Tool]:
        return self.tool_descriptions
