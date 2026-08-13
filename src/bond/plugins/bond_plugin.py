from abc import ABC

from bond.tools.tool import BondTool


class BondPlugin(ABC):

    def __init__(self):
        self._registered_tools: dict[str, BondTool] = {}

    def on_enable(self):
        pass

    def register_tool(self, tool: BondTool):
        self._registered_tools[tool.tool.function.name] = tool
