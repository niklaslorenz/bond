import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field
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
        persona = persona_type.model_validate(data)

        return persona

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
