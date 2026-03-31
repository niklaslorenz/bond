from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class StopSignal(BaseModel):
    type: Literal["stop"] = "stop"


class PromptSignal(BaseModel):
    type: Literal["prompt"] = "prompt"
    prompt: str


class CommandSignal(BaseModel):
    type: Literal["command"] = "command"
    command: str


BehaviourSignal = Annotated[
    Union[StopSignal, PromptSignal, CommandSignal], Field(discriminator="type")
]
SignalAdapter = TypeAdapter(BehaviourSignal)
