from pathlib import Path

from pydantic import BaseModel


class AskConfig(BaseModel):
    personas: list[str] = []
    default_persona: str | None = None
    tools: list[str] = []


class ChatConfig(BaseModel):
    personas: list[str] = []
    default_persona: str | None = None
    tools: list[str] = []


def get_default_persona(config: AskConfig | ChatConfig) -> str:
    if config.default_persona is not None:
        if not config.default_persona in config.personas:
            raise RuntimeError(
                "Default persona is not listed in allowed personas for bond"
            )
        return config.default_persona
    if len(config.personas) > 0:
        return config.personas[0]
    raise RuntimeError("No personas were configured for bond")


class BondConfig(BaseModel):
    ask: AskConfig = AskConfig()
    chat: ChatConfig = ChatConfig()
    user_name: str = "User"

    @classmethod
    def load_from(cls, config_path: Path) -> "BondConfig":
        return BondConfig.model_validate_json(config_path.read_text())
