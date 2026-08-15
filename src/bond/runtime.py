"""Bond Runtime - Central singleton for managing Bond's core registries and state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Type

from bond.registry import MappedEntryRegistry, NamedEntryRegistry

if TYPE_CHECKING:
    from bond.persona import Persona
    from bond.plugins.bond_plugin import BondPlugin
    from bond.tools.tool import BondTool

logger = logging.getLogger(__name__)


class BondRuntime:
    _instance: BondRuntime | None = None
    _persona_registry: NamedEntryRegistry[Type[Persona]]
    _tool_registry: MappedEntryRegistry[BondTool]
    _plugin_registry: NamedEntryRegistry[BondPlugin]

    def __new__(cls) -> BondRuntime:
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the runtime (only once due to singleton)."""
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._persona_registry = NamedEntryRegistry()
        self._tool_registry = MappedEntryRegistry(
            lambda tool: tool.description.function.name
        )
        self._plugin_registry = NamedEntryRegistry()
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

        Warning: This clears all registered types, tools, and plugins.
        """
        if cls._instance is not None:
            cls._instance._persona_registry.clear()
            cls._instance._tool_registry.clear()
            cls._instance._plugin_registry.clear()
        logger.debug("BondRuntime reset")

    @property
    def persona_registry(self) -> NamedEntryRegistry[Type[Persona]]:
        return self._persona_registry

    @property
    def tool_registry(self) -> MappedEntryRegistry[BondTool]:
        return self._tool_registry

    @property
    def plugin_registry(self) -> NamedEntryRegistry[BondPlugin]:
        return self._plugin_registry
