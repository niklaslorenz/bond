from pathlib import Path

from pydantic import BaseModel


class AskConfig(BaseModel):
    personas: list[str] = []
    default_persona: str | None = None
    tools: list[str] = []

    def get_default_persona(self) -> str:
        if self.default_persona is not None:
            if not self.default_persona in self.personas:
                raise RuntimeError(
                    "Default persona is not listed in allowed personas for bond ask"
                )
            return self.default_persona
        if len(self.personas) > 0:
            return self.personas[0]
        raise RuntimeError("No personas were configured for bond ask")


class BondConfig(BaseModel):
    ask: AskConfig = AskConfig()

    @classmethod
    def load_from(cls, config_path: Path) -> "BondConfig":
        return BondConfig.model_validate_json(config_path.read_text())
