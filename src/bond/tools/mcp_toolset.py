import asyncio
import logging
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.types import Tool as MCPTool

from bond.tools.tool import BondTool, ToolCallContext, ToolReturnType
from bond.tools.toolbox import Toolset

logger = logging.getLogger(__name__)


class McpToolset(Toolset):
    """A toolset that loads tools from an MCP server."""

    def __init__(self, name: str, server_params: StdioServerParameters):
        super().__init__(name)
        self._server_params = server_params
        self._session: ClientSession | None = None
        self._tools: list[BondTool] | None = None

    def initialize(self) -> list[BondTool]:
        """Initialize the MCP client and load tools."""
        if self._initialized:
            return self._tools or []

        try:
            self._session = ClientSession(
                self._server_params,
                initialization_options={
                    "server_name": f"bond-mcp-client-{self.name}",
                    "server_version": "0.1.0",
                },
            )
            asyncio.run(self._session.initialize())
            self._tools = self._load_mcp_tools()
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize MCP toolset '{self.name}': {e}")
            self._tools = []
            self._initialized = False

        return self._tools

    def _load_mcp_tools(self) -> list[BondTool]:
        """Load tools from the MCP server."""
        if not self._session:
            return []

        try:
            mcp_tools = asyncio.run(self._session.list_tools())
            return [McpToolAdapter(mcp_tool, self._session) for mcp_tool in mcp_tools]
        except Exception as e:
            logger.error(f"Failed to load MCP tools for toolset '{self.name}': {e}")
            return []

    def cleanup(self) -> None:
        """Close the MCP session."""
        if self._session:
            try:
                asyncio.run(self._session.close())
            except Exception as e:
                logger.error(f"Failed to clean up MCP toolset '{self.name}': {e}")
            finally:
                self._session = None
                self._tools = None
                self._initialized = False


class McpToolAdapter(BondTool):
    """Adapter to convert MCP tools into Bond tools."""

    def __init__(self, mcp_tool: MCPTool, session: ClientSession):
        # Convert MCP tool parameters to BondTool parameters format
        parameters = {}
        required = []

        for param_name, param_schema in mcp_tool.inputSchema.get(
            "properties", {}
        ).items():
            param_type = param_schema.get("type", "string")
            # Map MCP types to BondTool types
            if param_type == "integer":
                param_type = "number"  # BondTool uses "number" for both int and float
            elif param_type == "array":
                param_type = "array"
            elif param_type == "object":
                param_type = "object"

            parameters[param_name] = {
                "type": param_type,
                "description": param_schema.get("description", ""),
            }

            if param_name in mcp_tool.inputSchema.get("required", []):
                required.append(param_name)

        # Create the tool description
        from bond.tools.tool import Function, FunctionParameters
        from bond.tools.tool import Tool as BondToolModel

        tool_model = BondToolModel(
            function=Function(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                parameters=FunctionParameters(properties=parameters, required=required),
                strict=False,
            )
        )

        # Create the base function that will be called by BondTool
        async def mcp_tool_runner(
            context: ToolCallContext, **kwargs: Any
        ) -> ToolReturnType:
            """Execute the MCP tool with the given arguments."""
            try:
                # Convert kwargs to the format expected by MCP
                mcp_args = kwargs
                result = await session.call_tool(mcp_tool.name, mcp_args)
                return str(result) if result is not None else ""
            except Exception as e:
                logger.error(f"Failed to execute MCP tool '{mcp_tool.name}': {e}")
                raise

        # Initialize the BondTool with the base function and tool description
        super().__init__(mcp_tool_runner, tool_model)
        self.mcp_tool = mcp_tool
        self.session = session
