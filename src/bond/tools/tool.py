import asyncio
import os
import sys
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Concatenate,
    Generic,
    Literal,
    ParamSpec,
    TextIO,
)

from pydantic import BaseModel

from . import logger

if TYPE_CHECKING:
    from bond.behaviours.async_turn_event import (
        AsyncTurnEvent,
    )
    from bond.conversation.conversation import Conversation

ToolReturnType = str | list[str] | dict[str, Any] | list[dict[str, Any]] | None
ToolParameterType = Literal["string", "number", "integer", "boolean", "array", "object"]
ToolFn = Callable[..., ToolReturnType]


@dataclass
class ToolCallContext:
    persona: str
    stdout: TextIO | None
    stdin: TextIO | None
    is_interactive: bool
    cwd: Path | None
    logger: Logger | None
    confirmation_prompt: Callable[[str], bool] | None = None
    conversation: "Conversation | None" = None

    @classmethod
    def default(
        cls, persona: str, is_interactive: bool, conversation: "Conversation | None"
    ) -> "ToolCallContext":
        context = ToolCallContext(
            persona,
            sys.stdout,
            sys.stdin,
            is_interactive,
            Path(os.getcwd()),
            logger,
            None,
            conversation,
        )
        context.confirmation_prompt = context._terminal_confirmation
        return context

    @classmethod
    def async_default(
        cls,
        persona: str,
        is_interactive: bool,
        conversation: "Conversation | None",
        event_loop: asyncio.AbstractEventLoop,
        event_queue: "asyncio.Queue[AsyncTurnEvent]",
    ) -> "ToolCallContext":
        context = ToolCallContext(
            persona,
            None,
            None,
            is_interactive,
            Path(os.getcwd()),
            logger,
            None,
            conversation,
        )
        context.confirmation_prompt = lambda request: context._async_confirmation(
            event_loop, event_queue, request
        )
        return context

    def debug(self, msg: str):
        if self.logger:
            self.logger.debug(msg)

    def info(self, msg: str):
        if self.logger:
            self.logger.info(msg)

    def warning(self, msg: str):
        if self.logger:
            self.logger.warning(msg)

    def error(self, msg: str):
        if self.logger:
            self.logger.error(msg)

    def critical(self, msg: str):
        if self.logger:
            self.logger.critical(msg)

    def ask_confirmation(self, prompt: str) -> bool:
        if self.confirmation_prompt is None:
            return False
        return self.confirmation_prompt(prompt)

    def _terminal_confirmation(self, prompt: str) -> bool:
        if not self.is_interactive:
            return False
        print(prompt)
        try:
            while True:
                access = input("[yes|no] > ")
                if access == "yes" or access == "y":
                    return True
                if access == "no" or access == "n":
                    return False
                print("Invalid input.")
        except Exception as e:
            logger.error(e)
            return False

    def _async_confirmation(
        self,
        event_loop: asyncio.AbstractEventLoop,
        event_queue: "asyncio.Queue[AsyncTurnEvent]",
        prompt: str,
    ) -> bool:
        async def request() -> bool:
            result = event_loop.create_future()
            from bond.behaviours.async_turn_event import (
                AsyncTurnRequestConfirmationEvent,
            )

            await event_queue.put(AsyncTurnRequestConfirmationEvent(prompt, result))
            return await result

        if not self.is_interactive:
            return False
        result = asyncio.run_coroutine_threadsafe(request(), event_loop)
        return result.result()


class FunctionParameter(BaseModel):
    type: ToolParameterType
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


P = ParamSpec("P")


class BondTool(Generic[P]):

    def __init__(
        self,
        base_fn: Callable[Concatenate[ToolCallContext, P], ToolReturnType],
        tool: Tool,
    ):
        self.base_fn = base_fn
        self.description = tool

    def __call__(
        self, context: ToolCallContext, *args: P.args, **kwargs: P.kwargs
    ) -> ToolReturnType:
        return self.base_fn(context, *args, **kwargs)


def _build_tool(
    base_fn: Callable[Concatenate[ToolCallContext, P], ToolReturnType],
    name: str,
    description: str,
    parameters: dict[str, FunctionParameter],
    required: list[str] | None,
    strict: bool,
) -> BondTool[P]:
    tool = BondTool(
        base_fn,
        Tool(
            function=Function(
                name=name,
                description=description,
                parameters=FunctionParameters(
                    properties=parameters, required=required or []
                ),
                strict=strict,
            )
        ),
    )
    tool.__doc__ = description
    return tool


def tool(
    *,
    name: str,
    description: str,
    parameters: dict[str, FunctionParameter],
    required: list[str] | None = None,
    strict: bool = False,
):
    def build(
        base_fn: Callable[Concatenate[ToolCallContext, P], ToolReturnType],
    ) -> BondTool[P]:
        return _build_tool(
            base_fn,
            name=name,
            description=description,
            parameters=parameters,
            required=required,
            strict=strict,
        )

    return build
