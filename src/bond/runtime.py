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

from mcp import StdioServerParameters
from returns.result import Failure, Result, Success

from bond.config import (
    BondConfig,
    McpHttpServerConfig,
    McpStdioServerConfig,
)
from bond.local import find_local_bond_dir
from bond.persona import PersonaConfig
from bond.plugins.bond_plugin import BondPlugin
from bond.providers.mistral.mistral import Mistral
from bond.providers.ollama.ollama import Ollama
from bond.providers.provider import Provider
from bond.registry import MappedEntryRegistry, NamedEntryRegistry
from bond.skill import Skill
from bond.tools.file_system import (
    apply_patch,
    create_file,
    get_cwd,
    grep,
    list_directory,
    read_file,
    remove_file,
    tree,
)
from bond.tools.file_system.search import search_file
from bond.tools.local_tools import list_local_scripts, run_local_script
from bond.tools.mcp_toolset import McpToolset
from bond.tools.memory_tools import recall_memory, retire_memory, store_memory
from bond.tools.pdf_tools import pdf_info, read_pdf_text
from bond.tools.shell_tools import run_shell_commands
from bond.tools.skill_tools import load_skill, unload_skill
from bond.tools.stream_tools import write_to_output
from bond.tools.task_list import (
    add_tasks,
    clear_completed_tasks,
    clear_tasks,
    complete_tasks,
    delete_tasks,
)
from bond.tools.test_tool import test_confirmation
from bond.tools.toolbox import PythonToolset, Toolbox, Toolset
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web
from bond.tools.working_set import (
    add_working_set_directory,
    add_working_set_file,
    add_working_set_text,
    clear_working_set,
    remove_working_set_items,
)
from bond.vector_store.base import VectorStore

logger = logging.getLogger(__name__)

_default_toolsets: list[Toolset] = [
    PythonToolset("web", [search_the_web, access_web]),
    PythonToolset(
        "file",
        [
            list_directory,
            create_file,
            read_file,
            apply_patch,
            remove_file,
            get_cwd,
            search_file,
            grep,
            tree,
        ],
    ),
    PythonToolset("pdf", [pdf_info, read_pdf_text]),
    PythonToolset("shell", [run_shell_commands]),
    PythonToolset("local", [list_local_scripts, run_local_script]),
    PythonToolset("write", [write_to_output]),
    PythonToolset("test", [test_confirmation]),
    PythonToolset("memory", [recall_memory, store_memory, retire_memory]),
    PythonToolset("skills", [load_skill, unload_skill]),
    PythonToolset(
        "task_list",
        [add_tasks, complete_tasks, delete_tasks, clear_tasks, clear_completed_tasks],
    ),
    PythonToolset(
        "working_set",
        [
            add_working_set_text,
            add_working_set_file,
            add_working_set_directory,
            remove_working_set_items,
            clear_working_set,
        ],
    ),
]


_default_provider_types: dict[str, Type[Provider]] = {
    "mistral": Mistral,
    "ollama": Ollama,
}


class RuntimeEnvironment(ABC):
    @abstractmethod
    def get_bond_config(self) -> BondConfig: ...
    @abstractmethod
    def get_conversations_path(self) -> Path | None: ...
    @abstractmethod
    def get_cache_path(self) -> Path | None: ...
    @abstractmethod
    def list_providers(self) -> list[str]: ...
    @abstractmethod
    def list_personas(self) -> list[str]: ...
    @abstractmethod
    def list_prompts(self) -> list[str]: ...
    @abstractmethod
    def list_skills(self) -> list[str]: ...
    @abstractmethod
    def get_plugins(self) -> dict[str, BondPlugin]: ...
    @abstractmethod
    def load_provider(self, name: str, runtime: "BondRuntime") -> Provider: ...
    @abstractmethod
    def load_persona(
        self, name: str, runtime: "BondRuntime"
    ) -> Result[PersonaConfig, str]: ...
    @abstractmethod
    def load_prompt(self, name: str, runtime: "BondRuntime") -> str: ...
    @abstractmethod
    def load_skill(self, name: str, runtime: "BondRuntime") -> Result[Skill, str]: ...
    @abstractmethod
    def get_plugin_data_base_dir(self) -> Path: ...
    @abstractmethod
    def get_vector_stores_path(self) -> Path: ...


class StaticRuntimeEnvironment(RuntimeEnvironment):
    def __init__(
        self,
        bond_config: BondConfig,
        providers: dict[str, Provider],
        personas: dict[str, PersonaConfig],
        plugins: dict[str, BondPlugin],
        prompts: dict[str, str],
        data_dir: Path | None = None,
        conversations_path: Path | None = None,
        cache_path: Path | None = None,
        skills: dict[str, Skill] | None = None,
    ):
        self._bond_config = bond_config
        self._providers = providers
        self._personas = personas
        self._plugins = plugins
        self._prompts = prompts
        self._skills = skills or {}
        self._data_dir = data_dir or Path("~/.local/share/bond").expanduser().absolute()
        self._conversations_path = conversations_path
        self._cache_path = cache_path

    def get_bond_config(self) -> BondConfig:
        return self._bond_config

    def get_conversations_path(self) -> Path | None:
        return self._conversations_path

    def get_cache_path(self) -> Path | None:
        return self._cache_path

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def list_personas(self) -> list[str]:
        return list(self._personas.keys())

    def list_prompts(self) -> list[str]:
        return list(self._prompts.keys())

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def get_plugins(self) -> dict[str, BondPlugin]:
        return self._plugins.copy()

    def load_provider(self, name: str, runtime: "BondRuntime") -> Provider:
        return self._providers[name]

    def load_persona(
        self, name: str, runtime: "BondRuntime"
    ) -> Result[PersonaConfig, str]:
        return Result.from_value(self._personas[name])

    def load_prompt(self, name: str, runtime: "BondRuntime") -> str:
        return self._prompts[name]

    def load_skill(self, name: str, runtime: "BondRuntime") -> Result[Skill, str]:
        if name not in self._skills:
            return Result.from_failure(f"Invalid skill name: {name}")
        return Result.from_value(self._skills[name])

    def get_plugin_data_base_dir(self) -> Path:
        return self._data_dir

    def get_vector_stores_path(self) -> Path:
        return self._data_dir / "vector_stores"


class DynamicRuntimeEnvironment(RuntimeEnvironment):
    def __init__(self, config_dir: Path, data_base_dir: Path):
        self._config_dir = config_dir
        self._data_base_dir = data_base_dir
        self._bond_config = BondConfig.load_from(config_dir / "config.json")

    def get_bond_config(self) -> BondConfig:
        return self._bond_config

    def get_conversations_path(self) -> Path:
        return self._data_base_dir / "conversations"

    def get_cache_path(self) -> Path:
        return self._data_base_dir

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

    def list_prompts(self) -> list[str]:
        return [
            f[:-3]
            for f in glob.glob(
                "*.md", root_dir=(self._config_dir / "prompts").as_posix()
            )
        ]

    def list_skills(self) -> list[str]:
        skills_dir = self._config_dir / "skills"
        if not skills_dir.is_dir():
            return []
        return sorted(
            entry.name
            for entry in skills_dir.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        )

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
                        self.get_plugin_data_base_dir() / f"plugins/{plugin_ep.name}",
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

    def load_provider(self, name: str, runtime: "BondRuntime") -> Provider:
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
            provider_type.get_config_type().model_validate(data, extra="forbid")
        )

    def load_persona(
        self, name: str, runtime: "BondRuntime"
    ) -> Result[PersonaConfig, str]:
        path = self._config_dir / f"personas/{name}.json"
        return PersonaConfig.from_file_safe(path, runtime)

    def load_prompt(self, name: str, runtime: BondRuntime) -> str:
        path = self._config_dir / f"prompts/{name}.md"
        if not path.exists():
            raise ValueError(f"Invalid prompt name: {name}. Path does not exist.")
        return path.read_text(encoding="utf-8")

    def load_skill(self, name: str, runtime: BondRuntime) -> Result[Skill, str]:
        skill_path = self._config_dir / "skills" / name
        return Skill.load_from(skill_path, fallback_name=name)

    def get_plugin_data_base_dir(self) -> Path:
        return self._data_base_dir / "plugins"

    def get_vector_stores_path(self) -> Path:
        return self._data_base_dir / "vector_stores"


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
        self._persona_type_registry = NamedEntryRegistry[Type[PersonaConfig]]()
        self._provider_type_registry = NamedEntryRegistry[Type[Provider]]()
        self._toolset_registry = MappedEntryRegistry[Toolset](
            lambda toolset: toolset.name
        )
        self._loaded_plugins = NamedEntryRegistry[BondPlugin]()
        self._loaded_providers = NamedEntryRegistry[Provider]()
        self._loaded_personas = NamedEntryRegistry[PersonaConfig]()
        self._loaded_prompts = NamedEntryRegistry[str]()
        self._loaded_skills = NamedEntryRegistry[Skill]()
        self._local_skill_cache: dict[Path, Skill] = {}
        self._disable_local_config = False
        self._environment: RuntimeEnvironment | None = None
        logger.debug("BondRuntime created")

    def initialize_static(
        self,
        config: BondConfig,
        providers: dict[str, Provider],
        personas: dict[str, PersonaConfig],
        plugins: dict[str, BondPlugin],
        prompts: dict[str, str],
        skills: dict[str, Skill] | None = None,
        disable_local_config: bool = False,
    ) -> StaticRuntimeEnvironment:
        self._disable_local_config = disable_local_config
        self._environment = StaticRuntimeEnvironment(
            config, providers, personas, plugins, prompts, skills=skills
        )
        self._register_builtin_toolsets()
        self._register_builtin_provider_types()
        self._register_mcp_toolsets()
        self._load_plugins()
        return self._environment

    def initialize_dynamic(
        self,
        config_dir: Path | None = None,
        data_dir: Path | None = None,
        enable_plugins: bool = True,
        disable_local_config: bool = False,
    ) -> DynamicRuntimeEnvironment:
        if config_dir is None:
            config_dir = Path("~/.config/bond").expanduser().absolute()
        if data_dir is None:
            data_dir = Path("~/.local/share/bond").expanduser().absolute()
        self._disable_local_config = disable_local_config
        self._environment = DynamicRuntimeEnvironment(config_dir, data_dir)
        self._register_builtin_toolsets()
        self._register_builtin_provider_types()
        self._register_mcp_toolsets()
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

    def list_prompts(self) -> list[str]:
        return self._get_env().list_prompts()

    def list_skills(self) -> list[str]:
        """List all available skill names. Local skills from the closest
        ``.bond`` directory are included and shadow global skills of the
        same name."""
        names = set(self._get_env().list_skills())
        local_skills_path = self.get_local_skills_path()
        if local_skills_path is not None and local_skills_path.is_dir():
            for entry in local_skills_path.iterdir():
                if entry.is_dir() and (entry / "SKILL.md").is_file():
                    names.add(entry.name)
        return sorted(names)

    def list_local_skills(self) -> list[str]:
        """List the names of all local skills in the closest ``.bond/skills/``
        directory (subdirectories containing a ``SKILL.md``). Empty when local
        config is disabled (``disable_local_config``) or there is no ``.bond``
        directory."""
        local_skills_path = self.get_local_skills_path()
        if local_skills_path is None or not local_skills_path.is_dir():
            return []
        return sorted(
            entry.name
            for entry in local_skills_path.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        )

    def get_local_bond_dir(self) -> Path | None:
        """Return the closest ``.bond`` directory (searched from the current
        working directory upwards), or ``None`` if there is none or local
        config is disabled via ``disable_local_config``."""
        if self._disable_local_config:
            return None
        return find_local_bond_dir(Path.cwd())

    def get_local_skills_path(self) -> Path | None:
        bond_dir = self.get_local_bond_dir()
        return bond_dir / "skills" if bond_dir is not None else None

    def get_local_scripts_path(self) -> Path | None:
        bond_dir = self.get_local_bond_dir()
        return bond_dir / "scripts" if bond_dir is not None else None

    def get_local_conversations_path(self) -> Path | None:
        bond_dir = self.get_local_bond_dir()
        return bond_dir / "conversations" if bond_dir is not None else None

    def get_conversations_path(self) -> Path | None:
        return self._get_env().get_conversations_path()

    def get_cache_path(self) -> Path | None:
        return self._get_env().get_cache_path()

    def get_vector_stores_path(self) -> Path:
        return self._get_env().get_vector_stores_path()

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
    def persona_type_registry(self) -> NamedEntryRegistry[Type[PersonaConfig]]:
        return self._persona_type_registry

    @property
    def toolset_registry(self) -> MappedEntryRegistry[Toolset]:
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

    def get_persona(self, persona_name: str) -> Result[PersonaConfig, str]:
        """Get a persona by name, loading it if necessary."""
        env = self._get_env()
        if (persona := self._loaded_personas.get(persona_name)) is not None:
            return Result.from_value(persona)
        persona = env.load_persona(persona_name, self)
        if isinstance(persona, Success):
            self._loaded_personas.register(persona_name, persona.unwrap())
        return persona

    def get_provider(self, provider_name: str) -> Provider:
        """Get a provider by name, constructing it if necessary."""
        env = self._get_env()
        if (provider := self._loaded_providers.get(provider_name)) is not None:
            return provider
        provider = env.load_provider(provider_name, self)
        self._loaded_providers.register(provider_name, provider)
        return provider

    def get_prompt(self, prompt_name: str) -> str:
        """Get a prompt by name, loading it if necessary"""
        env = self._get_env()
        if (prompt := self._loaded_prompts.get(prompt_name)) is not None:
            return prompt
        prompt = env.load_prompt(prompt_name, self)
        self._loaded_prompts.register(prompt_name, prompt)
        return prompt

    def get_skill(self, skill_name: str) -> Result[Skill, str]:
        """Get a skill by name, loading it if necessary.

        A local skill from the closest ``.bond`` directory takes precedence
        over a global skill of the same name. Local skills are cached by
        their absolute path (not by name) so that a ``:cd`` into another
        project with a same-named local skill resolves correctly.
        """
        env = self._get_env()
        local_skills_path = self.get_local_skills_path()
        if local_skills_path is not None:
            local_skill_path = local_skills_path / skill_name
            if (local_skill_path / "SKILL.md").is_file():
                cached = self._local_skill_cache.get(local_skill_path)
                if cached is None:
                    result = Skill.load_from(
                        local_skill_path, fallback_name=skill_name
                    )
                    if isinstance(result, Failure):
                        return result
                    cached = result.unwrap()
                    self._local_skill_cache[local_skill_path] = cached
                return Result.from_value(cached)
        if (skill := self._loaded_skills.get(skill_name)) is not None:
            return Result.from_value(skill)
        skill = env.load_skill(skill_name, self)
        if isinstance(skill, Failure):
            return skill
        self._loaded_skills.register(skill_name, skill.unwrap())
        return skill

    def load_vector_store(self, name: str, vector_store_type: str) -> VectorStore:
        if vector_store_type != "faiss":
            raise ValueError(
                f"Unknown vector store type: {vector_store_type}. Only 'faiss' is supported."
            )
        from bond.vector_store.faiss_store import FAISSVectorStore

        path = self.get_vector_stores_path() / name
        return FAISSVectorStore.load_or_create(path)

    def _register_builtin_toolsets(self):
        for toolset in _default_toolsets:
            self._toolset_registry.register(toolset)

    def _register_builtin_provider_types(self):
        for k, v in _default_provider_types.items():
            self._provider_type_registry.register(k, v)

    def _register_mcp_toolsets(self):
        for mcp_toolset in self.get_bond_config().mcp:
            if isinstance(mcp_toolset, McpStdioServerConfig):
                server_parameter = StdioServerParameters(
                    command=mcp_toolset.command, args=mcp_toolset.args
                )
            elif isinstance(mcp_toolset, McpHttpServerConfig):
                server_parameter = mcp_toolset.uri
            self.toolset_registry.register(
                McpToolset(mcp_toolset.name, server_parameter)
            )

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
