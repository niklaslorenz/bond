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

from bond.config import (
    BondConfig,
)
from bond.persona import Persona
from bond.plugins.bond_plugin import BondPlugin
from bond.providers.mistral.mistral import Mistral
from bond.providers.ollama.ollama import Ollama
from bond.providers.provider import Provider
from bond.registry import NamedEntryRegistry
from bond.tools.fs_tools import (
    apply_patch,
    create_file,
    get_cwd,
    list_directory,
    read_file,
)
from bond.tools.shell_tools import run_shell_commands
from bond.tools.stream_tools import write_to_output
from bond.tools.toolbox import PythonToolset, Toolbox, Toolset
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web

logger = logging.getLogger(__name__)

_default_toolsets: dict[str, Toolset] = {
    t.name: t
    for t in [
        PythonToolset("web", [search_the_web, access_web]),
        PythonToolset(
            "file", [list_directory, create_file, read_file, apply_patch, get_cwd]
        ),
        PythonToolset("shell", [run_shell_commands]),
        PythonToolset("write", [write_to_output]),
    ]
}

_default_provider_types: dict[str, Type[Provider]] = {
    "mistral": Mistral,
    "ollama": Ollama,
}


class RuntimeEnvironment(ABC):
    @abstractmethod
    def get_bond_config(self) -> BondConfig: ...
    @abstractmethod
    def list_providers(self) -> list[str]: ...
    @abstractmethod
    def list_personas(self) -> list[str]: ...
    @abstractmethod
    def list_skills(self) -> list[str]: ...
    @abstractmethod
    def get_plugins(self) -> dict[str, BondPlugin]: ...
    @abstractmethod
    def load_provider(self, name: str, runtime: BondRuntime) -> Provider: ...
    @abstractmethod
    def load_persona(self, name: str, runtime: BondRuntime) -> Persona: ...
    @abstractmethod
    def load_skill(self, name: str, runtime: BondRuntime) -> str: ...
    @abstractmethod
    def get_data_dir(self) -> Path: ...


class StaticRuntimeEnvironment(RuntimeEnvironment):
    def __init__(
        self,
        bond_config: BondConfig,
        providers: dict[str, Provider],
        personas: dict[str, Persona],
        plugins: dict[str, BondPlugin],
        skills: dict[str, str],
        data_dir: Path | None = None,
    ):
        self._bond_config = bond_config
        self._providers = providers
        self._personas = personas
        self._plugins = plugins
        self._skills = skills
        self._data_dir = data_dir or Path("~/.local/share/bond").expanduser().absolute()

    def get_bond_config(self) -> BondConfig:
        return self._bond_config

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def list_personas(self) -> list[str]:
        return list(self._personas.keys())

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def get_plugins(self) -> dict[str, BondPlugin]:
        return self._plugins.copy()

    def load_provider(self, name: str, runtime: BondRuntime) -> Provider:
        return self._providers[name]

    def load_persona(self, name: str, runtime: BondRuntime) -> Persona:
        return self._personas[name]

    def load_skill(self, name: str, runtime: BondRuntime) -> str:
        return self._skills[name]

    def get_data_dir(self) -> Path:
        return self._data_dir


class DynamicRuntimeEnvironment(RuntimeEnvironment):
    def __init__(self, config_dir: Path):
        self._config_dir = config_dir
        self._bond_config = BondConfig.load_from(config_dir / "config.json")

    def get_bond_config(self) -> BondConfig:
        return self._bond_config

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

    def list_skills(self) -> list[str]:
        return [
            f[:-3]
            for f in glob.glob(
                "*.md", root_dir=(self._config_dir / "skills").as_posix()
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
        data = json.loads(path.read_text(encoding="utf-8"))
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
        return Persona.from_file(path, runtime)

    def load_skill(self, name: str, runtime: BondRuntime) -> str:
        path = self._config_dir / f"skills/{name}.md"
        if not path.exists():
            raise ValueError(f"Invalid skill name: {name}. Path does not exist.")
        return path.read_text(encoding="utf-8")

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
        self._loaded_skills = NamedEntryRegistry[str]()
        self._environment: RuntimeEnvironment | None = None
        logger.debug("BondRuntime created")

    def initialize_static(
        self,
        config: BondConfig,
        providers: dict[str, Provider],
        personas: dict[str, Persona],
        plugins: dict[str, BondPlugin],
        skills: dict[str, str],
    ) -> StaticRuntimeEnvironment:
        self._environment = StaticRuntimeEnvironment(
            config, providers, personas, plugins, skills
        )
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

    def get_bond_config(self) -> BondConfig:
        return self._get_env().get_bond_config()

    def list_providers(self) -> list[str]:
        return self._get_env().list_providers()

    def list_personas(self) -> list[str]:
        return self._get_env().list_personas()

    def list_plugins(self) -> list[str]:
        return self._plugin_registry.get_names()

    def list_skills(self) -> list[str]:
        return self._get_env().list_skills()

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

    def build_toolbox(self, toolset_names: list[str]) -> Toolbox:
        return Toolbox([self.get_toolset(name) for name in toolset_names])

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

    def get_skill(self, skill_name: str) -> str:
        """Get a skill by name, loading it if necessary"""
        env = self._get_env()
        if (skill := self._loaded_skills.get(skill_name)) is not None:
            return skill
        skill = env.load_skill(skill_name, self)
        self._loaded_skills.register(skill_name, skill)
        return skill

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
