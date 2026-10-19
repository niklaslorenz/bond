from pathlib import Path
from typing import Literal, Union

from pydantic import BaseModel, Field


class FrontendConfig(BaseModel):
    default_persona: str | None = None
    tools: list[str] = []


class McpServerConfigBase(BaseModel):
    name: str


class McpStdioServerConfig(McpServerConfigBase):
    type: Literal["stdio"] = "stdio"
    name: str
    command: str
    args: list[str]


class McpHttpServerConfig(McpServerConfigBase):
    type: Literal["http"] = "http"
    name: str
    uri: str


McpServerConfig = Union[McpStdioServerConfig, McpHttpServerConfig]


def get_default_persona(config: FrontendConfig) -> str:
    if config.default_persona is not None:
        return config.default_persona
    raise RuntimeError("No personas were configured for bond")


class BondConfig(BaseModel):
    ask: FrontendConfig = FrontendConfig()
    chat: FrontendConfig = FrontendConfig()
    mcp: list[McpServerConfig] = Field(default_factory=list)

    @classmethod
    def load_from(cls, config_path: Path) -> "BondConfig":
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if not config_path.exists():
            return BondConfig()
        return BondConfig.model_validate_json(
            config_path.read_text(encoding="utf-8"), extra="forbid"
        )
