"""Bond Runtime - Central singleton for managing Bond's core registries, state, and environment."""

from __future__ import annotations

import glob
import importlib
import importlib.metadata
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Type

from bond.persona import Persona
from bond.plugins.bond_plugin import BondPlugin
from bond.providers.mistral.mistral import Mistral
from bond.providers.ollama.ollama import Ollama
from bond.providers.provider import Provider
from bond.registry import NamedEntryRegistry
from bond.tools.fs_tools import (apply_patch, create_file, get_cwd,
                                 list_directory, read_file)
from bond.tools.shell_tools import run_shell_commands
from bond.tools.stream_tools import write_to_output
from bond.tools.tool import BondTool
from bond.tools.toolbox import Toolset
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web

logger = logging.getLogger(__name__)

_default_toolsets: dict[str, Toolset] = {
    "web": [search_the_web, access_web],
    "file": [list_directory, create_file, read_file, apply_patch, get_cwd],
    "shell": [run_shell_commands],
    "write": [write_to_output],
}

_default_provider_types: dict[str, Type[Provider]] = {
    "mistral": Mistral,
    "ollama": Ollama,
}


class RuntimeEnvironment(ABC):
    @abstractmethod
    def list_providers(self) -> list[str]: ...
    @abstractmethod
    def list_personas(self) -> list[str]: ...
    @abstractmethod
    def get_plugins(self) -> dict[str, BondPlugin]: ...
    @abstractmethod
    def load_provider(self, name: str, runtime: BondRuntime) -> Provider: ...
    @abstractmethod
    def load_persona(self, name: str, runtime: BondRuntime) -> Persona: ...
    @abstractmethod
    def get_data_dir(self) -> Path: ...


class StaticRuntimeEnvironment(RuntimeEnvironment):
    def __init__(
        self,
        providers: dict[str, Provider],
        personas: dict[str, Persona],
        plugins: dict[str, BondPlugin],
        data_dir: Path | None = None,
    ):
        self._providers = providers
        self._personas = personas
        self._plugins = plugins
        self._data_dir = data_dir or Path("~/.local/share/bond").expanduser().absolute()

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def list_personas(self) -> list[str]:
        return list(self._personas.keys())

    def get_plugins(self) -> dict[str, BondPlugin]:
        return self._plugins.copy()

    def load_provider(self, name: str, runtime: BondRuntime) -> Provider:
        return self._providers[name]

    def load_persona(self, name: str, runtime: BondRuntime) -> Persona:
        return self._personas[name]

    def get_data_dir(self) -> Path:
        return self._data_dir


class DynamicRuntimeEnvironment(RuntimeEnvironment):
    def __init__(self, config_dir: Path):
        self._config_dir = config_dir

    def list_providers(self) -> list[str]:
        return [
            f[:-5]
            for f in glob.glob(
                "*.json", root_dir=(self._config_dir / "providers").as_posix()
            )
        ]

    def list_personas(self) -> list[str]:
        return [
            f[:-5]
            for f in glob.glob(
                "*.json", root_dir=(self._config_dir / "personas").as_posix()
            )
        ]

    def get_plugins(self) -> dict[str, BondPlugin]:
        try:
            logger.debug("Discovering Plugins")
            entry_points = importlib.metadata.entry_points()
            bond_plugins = entry_points.select(group="bond.plugins")
            if not bond_plugins:
                logger.debug("No plugins found in entry points.")
                return {}
            plugins: dict[str, BondPlugin] = {}
            for plugin_ep in bond_plugins:
                try:
                    plugin_class = plugin_ep.load()
                    plugins[plugin_ep.name] = plugin_class(
                        BondRuntime.get_instance(),
                        self.get_data_dir() / f"plugins/{plugin_ep.name}",
                    )
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_ep.name}: {e}")
            logger.debug(
                "Found Plugins: " + ", ".join(name for name, _ in plugins.items())
            )
            return plugins
        except Exception as e:
            logger.error(f"Failed to load plugins: {e}")
        return {}

    def load_provider(self, name: str, runtime: BondRuntime) -> Provider:
        path = self._config_dir / f"providers/{name}.json"
        if not path.exists():
            raise ValueError(f"Invalid provider name: {name}. Path does not exist.")
        data = json.loads(path.read_text())
        if (provider_type_name := data.get("type")) is None:
            raise ValueError(
                f"Missing provider type in {path}. Valid values are {runtime._provider_type_registry.get_names()}"
            )
        if (
            provider_type := runtime._provider_type_registry.get(provider_type_name)
        ) is None:
            raise ValueError(
                f"Unknown provider type in {path}: {provider_type_name}. Valid values are {runtime._provider_type_registry.get_names()}"
            )
        return provider_type.from_config(
            provider_type.get_config_type().model_validate(data)
        )

    def load_persona(self, name: str, runtime: BondRuntime) -> Persona:
        path = self._config_dir / f"personas/{name}.json"
        if not path.exists():
            raise ValueError(f"Invalid persona name: {name}. Path does not exist.")
        data = json.loads(path.read_text())
        if (persona_type_name := data.get("type")) is not None:
            if (
                persona_type := runtime._persona_type_registry.get(persona_type_name)
            ) is None:
                raise ValueError(
                    f"Unknown persona type in {path}: {persona_type_name}. Valid values are {runtime._persona_type_registry.get_names()}"
                )
            return persona_type.model_validate(data)
        else:
            return Persona.model_validate(data)

    def get_data_dir(self) -> Path:
        return Path("~/.local/share/bond").expanduser().absolute()


class BondRuntime:

    _instance = None

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
        self._plugin_registry = NamedEntryRegistry[BondPlugin]()
        self._persona_type_registry = NamedEntryRegistry[Type[Persona]]()
        self._provider_type_registry = NamedEntryRegistry[Type[Provider]]()
        self._toolset_registry = NamedEntryRegistry[Toolset]()
        self._loaded_plugins = NamedEntryRegistry[BondPlugin]()
        self._loaded_providers = NamedEntryRegistry[Provider]()
        self._loaded_personas = NamedEntryRegistry[Persona]()
        self._environment: RuntimeEnvironment | None = None
        logger.debug("BondRuntime created")

    def initialize_static(
        self,
        providers: dict[str, Provider],
        personas: dict[str, Persona],
        plugins: dict[str, BondPlugin],
    ) -> StaticRuntimeEnvironment:
        self._environment = StaticRuntimeEnvironment(providers, personas, plugins)
        self._register_builtin_toolsets()
        self._register_builtin_provider_types()
        self._load_plugins()
        return self._environment

    def initialize_dynamic(
        self, config_dir: Path, enable_plugins: bool = True
    ) -> DynamicRuntimeEnvironment:
        self._environment = DynamicRuntimeEnvironment(config_dir)
        self._register_builtin_toolsets()
        self._register_builtin_provider_types()
        self._load_plugins(enable_plugins)
        return self._environment

    def list_providers(self) -> list[str]:
        return self._get_env().list_providers()

    def list_personas(self) -> list[str]:
        return self._get_env().list_personas()

    def list_plugins(self) -> list[str]:
        return self._plugin_registry.get_names()

    def get_data_dir(self) -> Path:
        return self._get_env().get_data_dir()

    @classmethod
    def get_instance(cls) -> BondRuntime:
        """Get the singleton BondRuntime instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def provider_type_registry(self) -> NamedEntryRegistry[Type[Provider]]:
        return self._provider_type_registry

    @property
    def persona_type_registry(self) -> NamedEntryRegistry[Type[Persona]]:
        return self._persona_type_registry

    @property
    def toolset_registry(self) -> NamedEntryRegistry[Toolset]:
        return self._toolset_registry

    @property
    def plugin_registry(self) -> NamedEntryRegistry[BondPlugin]:
        return self._plugin_registry

    def list_toolsets(self) -> list[str]:
        """List all available toolsets."""
        return list(self._toolset_registry.get_names())

    def get_toolset(self, toolset_name: str) -> Toolset:
        """Get a toolset by name."""
        toolset = self.toolset_registry.get(toolset_name)
        if toolset is None:
            raise ValueError(f"Unknown toolset name: {toolset_name}")
        return toolset

    def get_tools(self, toolset_names: list[str]) -> set[BondTool]:
        """Get tools from multiple toolsets."""
        tools = set()
        for tn in toolset_names:
            toolset = self.toolset_registry.get(tn)
            if toolset is not None:
                tools.update(toolset)
            else:
                logger.error(f"Unknown toolset name: {tn}")
        return tools

    def get_persona(self, persona_name: str) -> Persona:
        """Get a persona by name, loading it if necessary."""
        env = self._get_env()
        if (persona := self._loaded_personas.get(persona_name)) is not None:
            return persona
        persona = env.load_persona(persona_name, self)
        self._loaded_personas.register(persona_name, persona)
        return persona

    def get_provider(self, provider_name: str) -> Provider:
        """Get a provider by name, constructing it if necessary."""
        env = self._get_env()
        if (provider := self._loaded_providers.get(provider_name)) is not None:
            return provider
        provider = env.load_provider(provider_name, self)
        self._loaded_providers.register(provider_name, provider)
        return provider

    def _register_builtin_toolsets(self):
        for k, v in _default_toolsets.items():
            self._toolset_registry.register(k, v)

    def _register_builtin_provider_types(self):
        for k, v in _default_provider_types.items():
            self._provider_type_registry.register(k, v)

    def _load_plugins(self, enable_plugins: bool = True):
        for name, plugin in self._get_env().get_plugins().items():
            self._plugin_registry.register(name, plugin)
            if enable_plugins:
                try:
                    plugin.on_enable()
                    self._loaded_plugins.register(name, plugin)
                    logger.debug(f"Enabled plugin: {name}")
                except Exception as e:
                    logger.error(f"Failed to enable plugin {name}: {e}")

    def _get_env(self) -> RuntimeEnvironment:
        assert self._environment is not None, "Runtime not initialized"
        return self._environment
