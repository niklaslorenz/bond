from typing import Literal

from pydantic import BaseModel


class TuiEvent(BaseModel):
    type: str

    def get_type(self) -> str:
        return self.type


class UserInputEvent(TuiEvent):
    type: Literal["user_input"] = "user_input"
    input_type: Literal["command", "prompt"]
    message: str


class RequestConfirmEvent(TuiEvent):
    type: Literal["request_confirm"] = "request_confirm"
    accepted: bool


class StopEvent(TuiEvent):
    type: Literal["stop"] = "stop"
    immediately: bool


class StartEvent(TuiEvent):
    type: Literal["start"] = "start"
