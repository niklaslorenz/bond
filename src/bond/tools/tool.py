import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import local
from typing import Any, Callable, Literal, TextIO

from pydantic import BaseModel
from returns.result import Failure, Result, Success

from . import logger

ToolFn = Callable[..., str | list[str] | dict[str, Any] | list[dict[str, Any]]]
Toolset = list[ToolFn]


class FunctionParameter(BaseModel):
    type: Literal["string", "number", "integer", "boolean", "array", "object"]
    description: str


class FunctionParameters(BaseModel):
    type: Literal["object"]
    properties: dict[str, FunctionParameter]
    required: list[str] | None = None


class Function(BaseModel):
    name: str
    description: str = ""
    parameters: FunctionParameters
    strict: bool = False


class Tool(BaseModel):
    type: Literal["function"]
    function: Function


_tool_locals = local()


@dataclass
class BidirectionalTextIO:
    text_in: TextIO
    text_out: TextIO


@dataclass
class ToolEnvironment:
    tool_out: TextIO | None = None
    tool_in: TextIO | None = None
    shell_out: TextIO | None = None
    shell_in: TextIO | None = None
    interaction_io: BidirectionalTextIO | None = None
    work_dir: Path | Callable[[], Path] | None = None

    @contextmanager
    def activate(self):
        global _tool_locals
        if not hasattr(_tool_locals, "env"):
            _tool_locals.env = None
        old_env = _tool_locals.env
        _tool_locals.env = self
        try:
            yield
        finally:
            _tool_locals.env = old_env

    def ask_confirmation(self, prompt: str) -> bool:
        if self.interaction_io is None:
            return False
        self.interaction_io.text_out.write(prompt + "[yes|no] > ")
        try:
            while True:
                access = self.interaction_io.text_in.readline().strip(" \n")
                if access == "yes" or access == "y":
                    return True
                if access == "no" or access == "n":
                    return False
                self.interaction_io.text_out.write("\nInvalid input\n[yes|no] > ")
        except Exception as e:
            logger.error(e)
            return False

    def is_interactive(self) -> bool:
        return self.interaction_io is not None

    def get_work_dir(self) -> Path | None:
        if self.work_dir is None:
            return None
        if isinstance(self.work_dir, Path):
            return self.work_dir
        return self.work_dir()


def get_tool_environment() -> ToolEnvironment:
    global _tool_locals
    if not hasattr(_tool_locals, "env") or _tool_locals.env is None:
        raise RuntimeError("No tool environment")
    return _tool_locals.env


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
