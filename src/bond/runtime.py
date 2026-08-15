"""Bond Runtime - Central singleton for managing Bond's core registries and state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Type

if TYPE_CHECKING:
    from bond.persona import Persona
    from bond.tools.tool import BondTool

logger = logging.getLogger(__name__)


class BondRuntime:
    """
    Singleton class that holds Bond's core registries and state.

    The runtime is the central access point for:
    - Persona type registry (for plugin-extensible persona subclasses)
    - Tool registry (for plugin-provided tools)
    - Other registries as they are added

    Plugins receive a reference to the runtime via dependency injection,
    allowing them to register types, tools, etc. without relying on globals.

    Usage:
        # Get the singleton instance
        runtime = BondRuntime.get_instance()

        # Register a persona type
        runtime.persona_registry.register_type("my_type", MyPersonaClass)

        # Create a persona from dict
        persona = runtime.persona_registry.create_from_dict(data)
    """

    _instance: BondRuntime | None = None

    def __new__(cls) -> BondRuntime:
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the runtime (only once due to singleton)."""
        if self._initialized:
            return

        self._initialized = True
        self._persona_type_registry: dict[str, Type[Persona]] = {}
        self._tool_registry: dict[str, BondTool] = {}
        logger.debug("BondRuntime initialized")

    @classmethod
    def get_instance(cls) -> BondRuntime:
        """Get the singleton BondRuntime instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance. Primarily for testing.

        Warning: This clears all registered types and tools.
        """
        if cls._instance is not None:
            cls._instance._persona_type_registry.clear()
            cls._instance._tool_registry.clear()
            cls._instance._initialized = False
        cls._instance = None
        logger.debug("BondRuntime reset")

    @property
    def persona_registry(self) -> PersonaRegistry:
        """Get the persona type registry."""
        return PersonaRegistry(self._persona_type_registry)

    @property
    def tool_registry(self) -> ToolRegistry:
        """Get the tool registry."""
        return ToolRegistry(self._tool_registry)


class PersonaRegistry:
    """
    Registry for Persona subclasses.

    This allows plugins to define custom persona types with additional fields.
    The type string is used as a discriminator in persona JSON files.
    """

    def __init__(self, registry: dict[str, Type[Persona]]):
        self._registry = registry

    def register_type(
        self,
        persona_type: str,
        persona_class: Type[Persona],
    ) -> None:
        """
        Register a Persona subclass with a type discriminator.

        Args:
            persona_type: The type identifier
            persona_class: The Persona subclass to register

        Raises:
            ValueError: If the type is already registered
        """
        if persona_type in self._registry:
            raise ValueError(
                f"Persona type '{persona_type}' is already registered to "
                f"{self._registry[persona_type].__name__}"
            )

        self._registry[persona_type] = persona_class
        logger.debug(
            f"Registered persona type: {persona_type} -> {persona_class.__name__}"
        )

    def unregister_type(self, persona_type: str) -> bool:
        """
        Unregister a persona type.

        Args:
            persona_type: The type identifier to unregister

        Returns:
            True if the type was registered and removed, False otherwise
        """
        if persona_type in self._registry:
            del self._registry[persona_type]
            logger.debug(f"Unregistered persona type: {persona_type}")
            return True
        return False

    def get_type(self, persona_type: str) -> Type[Persona] | None:
        """
        Get the Persona subclass registered for a given type.

        Args:
            persona_type: The type identifier

        Returns:
            The Persona subclass if registered, None otherwise
        """
        return self._registry.get(persona_type)

    def get_all_types(self) -> dict[str, Type[Persona]]:
        """
        Get all registered persona types.

        Returns:
            A copy of the registry dictionary
        """
        return self._registry.copy()

    def get_class_for_data(self, data: dict[str, Any]) -> Type[Persona]:
        """
        Determine the appropriate Persona class based on the type discriminator.

        Args:
            data: The parsed JSON data

        Returns:
            The Persona subclass to use for deserialization

        Raises:
            ValueError: If the type is not registered or missing
        """
        from bond.persona import Persona

        persona_type = data.get("type")

        if persona_type is None or persona_type == "default":
            return Persona

        if persona_type not in self._registry:
            raise ValueError(
                f"Unknown persona type '{persona_type}'. "
                f"Available types: {list(self._registry.keys())}"
            )

        return self._registry[persona_type]

    def create_from_dict(self, data: dict[str, Any]) -> Persona:
        """
        Create a Persona instance from a dictionary, using the registered type.

        This is the recommended way to load personas as it respects the
        discriminated union pattern.

        Args:
            data: The persona data as a dictionary

        Returns:
            A Persona instance (or subclass instance)

        Raises:
            ValueError: If the type is invalid or data is malformed
        """
        persona_class = self.get_class_for_data(data)
        return persona_class.model_validate(data)


class ToolRegistry:
    """
    Registry for Bond tools.

    This allows plugins to register custom tools.
    """

    def __init__(self, registry: dict[str, BondTool]):
        self._registry = registry

    def register(self, tool: BondTool) -> None:
        """
        Register a tool.

        Args:
            tool: The BondTool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        name = tool.description.function.name
        if name in self._registry:
            raise ValueError(f"Tool '{name}' is already registered")

        self._registry[name] = tool
        logger.debug(f"Registered tool: {name}")

    def unregister(self, tool_name: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: The name of the tool to unregister

        Returns:
            True if the tool was registered and removed, False otherwise
        """
        if tool_name in self._registry:
            del self._registry[tool_name]
            logger.debug(f"Unregistered tool: {tool_name}")
            return True
        return False

    def get(self, tool_name: str) -> BondTool | None:
        """
        Get a registered tool by name.

        Args:
            tool_name: The name of the tool

        Returns:
            The BondTool if registered, None otherwise
        """
        return self._registry.get(tool_name)

    def get_all(self) -> dict[str, BondTool]:
        """
        Get all registered tools.

        Returns:
            A copy of the registry dictionary
        """
        return self._registry.copy()
