import glob
from pathlib import Path
from typing import Protocol

from bond.persona import Persona
from bond.plugins.registry import get_plugins
from bond.providers.provider import (
    Provider,
    ProviderConfig,
    construct_provider,
    load_config_from,
)
from bond.runtime import BondRuntime
from bond.tools.tool import BondTool, ToolFn
from bond.tools.toolbox import Toolset

from . import logger


class BondEnvironment(Protocol):
    def list_toolsets(self) -> list[str]: ...
    def list_personas(self) -> list[str]: ...
    def list_providers(self) -> list[str]: ...
    def get_toolset(self, toolset_name: str) -> Toolset: ...
    def get_tools(self, toolset_names: list[str]) -> set[BondTool]: ...
    def get_persona(self, persona_name: str) -> Persona: ...
    def get_provider(self, provider_name: str) -> Provider: ...


class StaticBondEnvironment:
    def __init__(
        self,
        providers: dict[str, Provider],
        personas: dict[str, Persona],
        tools: dict[str, Toolset],
    ):
        self.providers = providers
        self.personas = personas
        self.tools = tools
        # Get the runtime to ensure it's initialized
        self._runtime = BondRuntime.get_instance()
        # Ensure plugins are loaded so their persona types are registered
        get_plugins()

    @property
    def runtime(self) -> BondRuntime:
        """Get the BondRuntime instance."""
        return self._runtime

    def list_toolsets(self) -> list[str]:
        return list(self.tools.keys())

    def list_personas(self) -> list[str]:
        return list(self.personas.keys())

    def list_providers(self) -> list[str]:
        return list(self.providers.keys())

    def get_toolset(self, toolset_name: str) -> list[ToolFn]:
        return self.tools[toolset_name]

    def get_tools(self, toolset_names: list[str]) -> set[BondTool]:
        for tn in toolset_names:
            if tn not in self.tools:
                logger.error(f"Unknown toolset name: {tn}")
        return {t for tn in toolset_names for t in self.tools.get(tn) or []}

    def get_persona(self, persona_name: str) -> Persona:
        return self.personas[persona_name]

    def get_provider(self, provider_name: str) -> Provider:
        return self.providers[provider_name]


class DynamicBondEnvironment:
    base_path: Path
    tools: dict[str, Toolset]
    provider_names: list[str] | None = None
    provider_configs: dict[str, ProviderConfig] = {}
    providers: dict[str, Provider] = {}
    persona_names: list[str] | None = None
    personas: dict[str, Persona] = {}

    def __init__(self, environment_path: Path, tools: dict[str, Toolset]):
        self.base_path = environment_path.expanduser().absolute()
        self.tools = tools
        # Get the runtime to ensure it's initialized
        self._runtime = BondRuntime.get_instance()
        # Ensure plugins are loaded so their persona types are registered
        get_plugins()

    @property
    def runtime(self) -> BondRuntime:
        """Get the BondRuntime instance."""
        return self._runtime

    def list_toolsets(self) -> list[str]:
        return list(self.tools.keys())

    def list_personas(self) -> list[str]:
        if self.persona_names is None:
            self.persona_names = self._discover_personas()
        return self.persona_names.copy()

    def list_providers(self) -> list[str]:
        if self.provider_names is None:
            self.provider_names = self._discover_providers()
        return self.provider_names

    def clear_cache(self):
        self.provider_names = None
        self.persona_names = None

    def get_toolset(self, toolset_name: str) -> Toolset:
        return self.tools[toolset_name]

    def get_tools(self, toolset_names: list[str]) -> set[BondTool]:
        for tn in toolset_names:
            if tn not in self.tools:
                logger.error(f"Unknown toolset name: {tn}")
        return {t for tn in toolset_names for t in self.tools.get(tn) or []}

    def get_persona(self, persona_name: str) -> Persona:
        persona = self.personas.get(persona_name)
        if persona is not None:
            return persona
        persona = Persona.load_from(self._get_persona_path(persona_name))
        self.personas[persona_name] = persona
        return persona

    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        config = self.provider_configs.get(provider_name)
        if config is not None:
            return config
        config = load_config_from(self._get_provider_config_path(provider_name))
        self.provider_configs[provider_name] = config
        return config

    def get_provider(self, provider_name: str) -> Provider:
        provider = self.providers.get(provider_name)
        if provider is not None:
            return provider
        config = self.get_provider_config(provider_name)
        provider = construct_provider(config)
        self.providers[provider_name] = provider
        return provider

    def _get_persona_path(self, persona: str):
        return self.base_path / "personas" / f"{persona}.json"

    def _get_provider_config_path(self, provider: str):
        return self.base_path / "providers" / f"{provider}.json"

    def _discover_personas(self) -> list[str]:
        return [
            f[:-5]
            for f in glob.glob(
                "*.json", root_dir=(self.base_path / "personas").as_posix()
            )
        ]

    def _discover_providers(self) -> list[str]:
        return [
            f[:-5]
            for f in glob.glob(
                "*.json", root_dir=(self.base_path / "providers").as_posix()
            )
        ]
