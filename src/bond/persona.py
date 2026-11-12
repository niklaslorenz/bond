import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from returns.result import Failure, Result, Success

from bond.capabilities.generation import GenerationCapability
from bond.capabilities.memory import MemoryCapability
from bond.capabilities.summarization import SummarizationCapability
from bond.capabilities.thought_condensation import ThoughtCondensationCapability
from bond.capabilities.tts import TTSCapability
from bond.tools.toolbox import Toolbox

if TYPE_CHECKING:
    from bond.providers.provider import Provider
    from bond.runtime import BondRuntime

MANAGED_DIR_URI_PREFIX = "bond://"
"""URI prefix for addressing persona-managed directories: ``bond://<name>/<path>``."""


class ManagedDirectory(BaseModel):
    """A directory the persona can always access via ``bond://<name>/<path>``."""

    name: str
    path: str
    read_only: bool = False

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value or "/" in value or value in (".", ".."):
            raise ValueError(
                f"Invalid managed directory name {value!r}: must be non-empty, "
                "contain no '/' and not be '.' or '..'"
            )
        return value

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if not value:
            raise ValueError("Managed directory path must not be empty")
        return value


def _managed_root_of(managed_dir: ManagedDirectory) -> Path:
    """Normalized absolute root of a managed directory.

    Lexical only — symlinks are deliberately not resolved so that symlinked
    roots/targets keep working.
    """
    return Path(os.path.normpath(Path(managed_dir.path).expanduser().absolute()))


@dataclass
class Persona:
    name: str
    config: "PersonaConfig"
    generation: GenerationCapability
    summarization: SummarizationCapability | None
    thought_condensation: ThoughtCondensationCapability | None
    tts: TTSCapability | None
    memory: MemoryCapability | None
    toolsets: list[str]
    runtime: "BondRuntime"
    managed_directories: list[ManagedDirectory] = field(default_factory=list)

    def release(self):
        if self.memory is not None:
            self.memory.release()

    def build_toolbox(self) -> Toolbox:
        return self.runtime.build_toolbox(self.toolsets)

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve a path, mapping ``bond://<name>/<sub>`` URIs onto managed directories.

        Paths without the ``bond://`` prefix are returned as-is. Raises
        ``ValueError`` for unknown managed directory names and for URIs that
        lexically escape the managed root (e.g. via ``..``). Containment is
        checked lexically (no symlink resolution), so symlinked roots keep
        working.
        """
        raw = str(path)
        if not raw.startswith(MANAGED_DIR_URI_PREFIX):
            return Path(raw)
        rest = raw[len(MANAGED_DIR_URI_PREFIX) :]
        name, _, sub = rest.partition("/")
        for managed_dir in self.managed_directories:
            if managed_dir.name == name:
                root = _managed_root_of(managed_dir)
                break
        else:
            raise ValueError(
                f"Unknown managed directory '{name}'. Available: "
                f"{[md.name for md in self.managed_directories]}"
            )
        target = Path(os.path.normpath(root / sub))
        if not target.is_relative_to(root):
            raise ValueError(f"Path '{raw}' escapes managed directory '{name}'")
        return target

    def managed_directory_for(self, path: Path) -> ManagedDirectory | None:
        """Return the managed directory whose root lexically contains ``path``."""
        p = Path(os.path.normpath(Path(path).expanduser()))
        if not p.is_absolute():
            return None
        for managed_dir in self.managed_directories:
            if p.is_relative_to(_managed_root_of(managed_dir)):
                return managed_dir
        return None


class ConversationFeatures(BaseModel):
    task_list: bool = False
    working_set: bool = False


class PersonaConfig(BaseModel):
    type: ClassVar[str] = "default"

    name: str
    conversation_features: ConversationFeatures = Field(
        default_factory=ConversationFeatures
    )

    generation: dict[str, Any]
    summarization: dict[str, Any] | None = None
    thought_condensation: dict[str, Any] | None = None
    tts: dict[str, Any] | None = None
    voice_input: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None

    toolsets: list[str] = Field(default_factory=list)
    available_skills: list[str] = Field(default_factory=list)
    managed_directories: list[ManagedDirectory] = Field(default_factory=list)
    """Managed directories the persona can always access via ``bond://<name>/<path>``."""
    use_local_skills: bool = False
    """When True, all local skills from the closest ``.bond/skills/`` are
    considered available in conversations that do not define their own
    ``available_skills`` list (a conversation-level list still takes
    precedence). When False (default), only ``available_skills`` apply."""

    @model_validator(mode="after")
    def _unique_managed_directory_names(self) -> "PersonaConfig":
        names = [md.name for md in self.managed_directories]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"Duplicate managed directory names: {duplicates}")
        return self

    @classmethod
    def get_type(cls) -> str:
        """Get the type discriminator for this persona class."""
        return getattr(cls, "type", "default")

    @classmethod
    def from_file(cls, file: Path, runtime: "BondRuntime | None"):
        if runtime is None:
            from bond.runtime import BondRuntime

            runtime = BondRuntime.get_instance()
        if not file.exists():
            raise ValueError(
                f"Could not load persona from file: '{file}'. Does not exist."
            )
        data = json.loads(file.read_text(encoding="utf-8"))
        if (persona_type_name := data.get("type")) is not None:
            if (
                persona_type := runtime._persona_type_registry.get(persona_type_name)
            ) is None:
                raise ValueError(
                    f"Unknown persona type in {file}: {persona_type_name}. Valid values are {runtime._persona_type_registry.get_names()}"
                )
        else:
            persona_type = PersonaConfig
        persona = persona_type.model_validate(data, extra="forbid")

        return persona

    @classmethod
    def from_file_safe(
        cls, file: Path, runtime: "BondRuntime | None" = None
    ) -> Result["PersonaConfig", str]:
        """
        Safely load a PersonaConfig from a file, returning a Result with a user-friendly error message on failure.

        This is a wrapper around from_file that catches exceptions and converts them to
        understandable error messages. Unlike from_file, this method will never raise an exception
        and instead returns a Failure with a descriptive error message.

        Args:
            file: Path to the persona configuration file
            runtime: Optional BondRuntime instance

        Returns:
            Success with the loaded PersonaConfig on success, or Failure with an error message on failure
        """

        try:
            config = cls.from_file(file, runtime)
            return Success(config)
        except json.JSONDecodeError as e:
            # Handle JSON parsing errors
            return Failure(f"Invalid JSON in file '{file}': {str(e)}")
        except ValidationError as e:
            # Handle pydantic validation errors - format them nicely
            errors = []
            for error in e.errors():
                loc = " -> ".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                errors.append(f"  - Field '{loc}': {msg}")
            error_list = "\n".join(errors)
            return Failure(f"Invalid persona configuration in '{file}':\n{error_list}")
        except ValueError as e:
            # Handle file not found and unknown persona type errors
            error_msg = str(e)
            if "Does not exist" in error_msg:
                return Failure(f"File not found: '{file}'")
            elif "Unknown persona type" in error_msg:
                return Failure(error_msg)
            return Failure(f"Configuration error: {error_msg}")
        except Exception as e:
            # Catch any other unexpected errors
            return Failure(f"Unexpected error loading persona from '{file}': {str(e)}")

    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON, including the type discriminator."""
        data = self.model_dump(**kwargs)
        persona_type = self.get_type()
        if persona_type != "default":
            data = {"type": persona_type, **data}
        return json.dumps(data, **kwargs)

    def instantiate(self, runtime: "BondRuntime | None" = None):
        if runtime is None:
            from bond.runtime import BondRuntime

            runtime = BondRuntime.get_instance()
        generation = (
            _get_provider(self.generation, runtime)
            .map(lambda x: x.generation(self.name, self.generation, runtime))
            .value_or(None)
        )
        if generation is None:
            raise RuntimeError("Provider does not support generation")
        summarization = (
            _get_provider(self.summarization, runtime)
            .map(lambda x: x.summarization(self.summarization or {}, runtime))
            .value_or(None)
        )
        thought_condensation = (
            _get_provider(self.thought_condensation, runtime)
            .map(
                lambda x: x.thought_condensation(
                    self.thought_condensation or {}, runtime
                )
            )
            .value_or(None)
        )
        tts = (
            _get_provider(self.tts, runtime)
            .map(lambda x: x.tts(self.tts or {}, runtime))
            .value_or(None)
        )
        memory = (
            _get_provider(self.memory, runtime)
            .map(lambda x: x.memory(self.memory or {}, runtime))
            .value_or(None)
        )
        return Persona(
            self.name,
            self,
            generation,
            summarization,
            thought_condensation,
            tts,
            memory,
            self.toolsets,
            runtime,
            managed_directories=self.managed_directories,
        )


def _get_provider(
    config: dict[str, Any] | None, runtime: "BondRuntime"
) -> "Result[Provider, None]":
    if config is None:
        return Failure(None)
    if (provider := config.get("provider")) is not None:
        return Success(runtime.get_provider(provider))
    return Failure(None)
