from abc import ABC
from typing import TYPE_CHECKING, Type

from bond.persona import Persona
from bond.tools.tool import BondTool

if TYPE_CHECKING:
    from bond.runtime import BondRuntime


class BondPlugin(ABC):
    """
    Base class for Bond plugins.

    Plugins can extend Bond's functionality by:
    - Registering custom tools via `register_tool()`
    - Registering custom persona types via `register_persona_type()`
    - Overriding `on_enable()` for initialization logic

    Plugins receive a BondRuntime instance via dependency injection,
    which provides access to registries and other runtime services.
    """

    def __init__(self, runtime: "BondRuntime"):
        self._runtime = runtime
        self._registered_tools: dict[str, BondTool] = {}
        self._registered_persona_types: dict[str, Type[Persona]] = {}

    def on_enable(self):
        """
        Called when the plugin is enabled.

        Override this method to perform plugin initialization,
        such as registering persona types with the global registry.
        """
        pass

    def register_tool(self, tool: BondTool):
        """
        Register a tool with this plugin and the runtime's tool registry.

        Args:
            tool: The BondTool instance to register
        """
        self._registered_tools[tool.description.function.name] = tool
        self._runtime.tool_registry.register(tool)

    def register_persona_type(
        self,
        persona_type: str,
        persona_class: Type[Persona],
    ) -> None:
        """
        Register a custom Persona subclass with a type discriminator.

        This allows the plugin to define persona types with additional fields.
        The type will be registered with the runtime's persona registry.
        If the plugin has a runtime reference, it uses that; otherwise,
        it falls back to the global runtime singleton.

        Args:
            persona_type: The type identifier (e.g., "my_plugin_persona")
            persona_class: The Persona subclass to register

        Raises:
            ValueError: If the type is already registered or class is invalid
        """
        if not issubclass(persona_class, Persona):
            raise ValueError(
                f"Cannot register {persona_class.__name__}: not a subclass of Persona"
            )

        if persona_type in self._registered_persona_types:
            raise ValueError(
                f"Persona type '{persona_type}' is already registered with this plugin"
            )

        self._runtime.persona_registry.register_type(persona_type, persona_class)
        self._registered_persona_types[persona_type] = persona_class

    def get_registered_tools(self) -> dict[str, BondTool]:
        """Get all tools registered with this plugin."""
        return self._registered_tools.copy()

    def get_registered_persona_types(self) -> dict[str, Type[Persona]]:
        """Get all persona types registered with this plugin."""
        return self._registered_persona_types.copy()
