import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field, ValidationError
from returns.result import Failure, Result, Success

from bond.capabilities.generation import GenerationCapability
from bond.capabilities.summarization import SummarizationCapability
from bond.capabilities.tts import TTSCapability
from bond.tools.toolbox import Toolbox

if TYPE_CHECKING:
    from bond.providers.provider import Provider
    from bond.runtime import BondRuntime


class Persona:
    def __init__(
        self,
        name: str,
        config: "PersonaConfig",
        generation: GenerationCapability,
        summarization: SummarizationCapability | None,
        tts: TTSCapability | None,
        toolbox: Toolbox,
    ):
        self.name = name
        self.config = config
        self.generation = generation
        self.summarization = summarization
        self.tts = tts
        self.toolbox = toolbox


class PersonaConfig(BaseModel):
    type: ClassVar[str] = "default"

    name: str

    generation: dict[str, Any]
    summarization: dict[str, Any] | None = None
    tts: dict[str, Any] | None = None
    voice_input: dict[str, Any] | None = None

    toolsets: list[str] = Field(default_factory=list)

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
        toolbox = runtime.build_toolbox(self.toolsets)
        generation = (
            _get_provider(self.generation, runtime)
            .map(lambda x: x.generation(self.name, self.generation, toolbox, runtime))
            .value_or(None)
        )
        if generation is None:
            raise RuntimeError("Provider does not support generation")
        summarization = (
            _get_provider(self.summarization, runtime)
            .map(lambda x: x.summarization(self.summarization or {}, runtime))
            .value_or(None)
        )
        tts = (
            _get_provider(self.tts, runtime)
            .map(lambda x: x.tts(self.tts or {}, runtime))
            .value_or(None)
        )
        return Persona(self.name, self, generation, summarization, tts, toolbox)


def _get_provider(
    config: dict[str, Any] | None, runtime: "BondRuntime"
) -> "Result[Provider, None]":
    if config is None:
        return Failure(None)
    if (provider := config.get("provider")) is not None:
        return Success(runtime.get_provider(provider))
    return Failure(None)
