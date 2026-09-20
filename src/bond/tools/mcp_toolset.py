import asyncio
import traceback
from threading import Thread
from typing import Any, Protocol, runtime_checkable

from mcp import ClientSession
from mcp import Tool as McpTool
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from bond.tools.tool import (
    BondTool,
    Function,
    FunctionParameter,
    FunctionParameters,
    Tool,
    ToolCallContext,
    ToolParameterType,
)
from bond.tools.toolbox import ActiveToolset, Toolset

from . import logger


class ActiveMcpToolset(ActiveToolset):

    def __init__(self, connection_parameter: StdioServerParameters | str):
        self._connection_parameter = connection_parameter
        self._thread = Thread(target=self._run_event_loop, daemon=True)
        self._loop = asyncio.new_event_loop()
        self._transport = None
        self._session = None
        self.connect()

        tools = self.list_tools()
        super().__init__(tools)

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro):
        future = asyncio.run_coroutine_threadsafe(
            coro,
            self._loop,
        )
        return future.result()

    async def _connect(self):
        if self._session is not None:
            logger.warning(
                "Tried to connect an already connected ActiveMcpToolset again"
            )
            return
        if isinstance(self._connection_parameter, StdioServerParameters):
            self._transport = stdio_client(self._connection_parameter)
        else:
            self._transport = streamable_http_client(self._connection_parameter)
        read_stream, write_stream, *_ = await self._transport.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        try:
            await self._session.initialize()
        except Exception:
            await self._session.__aexit__(None, None, None)
            await self._transport.__aexit__(None, None, None)
            self._session = None
            self._transport = None
            raise

    async def _close(self):
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None

        if self._transport is not None:
            await self._transport.__aexit__(None, None, None)
            self._transport = None

    async def _call_tool(self, name: str, arguments: dict[str, Any] | None):
        if self._session is None:
            raise RuntimeError("Not connected")

        return await self._session.call_tool(
            name,
            arguments,
        )

    async def _list_tools(self) -> list[BondTool]:
        if self._session is None:
            raise RuntimeError("Not connected")

        return list(
            filter(
                None,
                map(self._parse_mcp_tool, (await self._session.list_tools()).tools),
            )
        )

    def _parse_mcp_parameter(
        self, parameter: dict[str, Any]
    ) -> tuple[FunctionParameter, bool]:
        description = parameter["description"]
        if (parameter_enum := parameter.get("enum")) is not None:
            description += f"\nAllowed Values: [{', '.join(parameter_enum)}]"
        function_type, is_optional = _handle_mcp_parameter_type(parameter["type"])
        return (
            FunctionParameter(type=function_type, description=description),
            is_optional,
        )

    def _parse_mcp_tool(self, tool: McpTool) -> BondTool | None:
        try:
            parsed_parameters: dict[str, tuple[FunctionParameter, bool]] = (
                {k: self._parse_mcp_parameter(v) for k, v in properties.items()}
                if (properties := tool.input_schema.get("properties")) is not None
                else {}
            )
            parameters = {k: param for k, (param, _) in parsed_parameters.items()}
            additional_optional_parameters = set(
                k for (k, (_, is_optional)) in parsed_parameters.items() if is_optional
            )
            required_parameters = list(
                set(tool.input_schema.get("required") or set())
                - additional_optional_parameters
            )
            function_parameters = FunctionParameters(
                properties=parameters, required=required_parameters
            )
            tool_description = Tool(
                function=Function(
                    name=tool.name,
                    description=tool.description or "<No description found>",
                    parameters=function_parameters,
                )
            )
        except Exception as e:
            logger.error(
                f"Unable to parse mcp tool:{{{tool}}}\n\n{type(e)}: {e}\n{traceback.format_exc()}"
            )
            return None

        def call_tool(context: ToolCallContext, **kwargs):
            call_result = self.call_tool(tool.name, kwargs)
            return "\n".join(
                block.text
                for block in call_result.content
                if isinstance(block, TextContent)
            )

        bond_tool = BondTool(call_tool, tool_description)
        return bond_tool

    # Synchronous API

    def connect(self):
        if self._thread.is_alive():
            logger.warning(
                "Tried to connect an already connected ActiveMcpToolset again"
            )
            return
        self._thread.start()
        self._run_async(self._connect())

    def release(self):
        self._run_async(self._close())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()

    def call_tool(self, name: str, arguments: dict[str, Any] | None):
        return self._run_async(self._call_tool(name, arguments))

    def list_tools(self):
        return self._run_async(self._list_tools())


class McpToolset(Toolset[ActiveMcpToolset]):
    def __init__(
        self,
        name: str,
        connection_parameter: StdioServerParameters | str,
    ):
        super().__init__(name)
        self._connection_parameter = connection_parameter

    def activate(self) -> ActiveMcpToolset:
        return ActiveMcpToolset(self._connection_parameter)


# TODO: Make this more resilient to unexpected values and log detailed descriptions
# of when the value cant accurately be parsed to prevent silent failures.
def _handle_mcp_parameter_type(mcp_type: Any) -> tuple[ToolParameterType, bool]:
    if isinstance(mcp_type, list):
        if len(mcp_type) == 0:
            raise ValueError("Empty type is not supported")
        if len(mcp_type) == 1:
            return _handle_mcp_parameter_type(mcp_type[0])
        else:
            first = mcp_type[0]
            return _handle_mcp_parameter_type(
                first if first != "null" else mcp_type[1]
            )[0], ("null" in mcp_type)
    if isinstance(mcp_type, str):
        if mcp_type in ("string", "number", "integer", "boolean", "array", "object"):
            return mcp_type, False
    raise ValueError(f"Unknown parameter type: {mcp_type}")
