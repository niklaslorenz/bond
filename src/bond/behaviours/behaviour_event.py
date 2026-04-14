"""Behaviour Events are sent from the loop behaviour to the event queue."""

from concurrent.futures import Future
from typing import Literal

from pydantic import PrivateAttr

from bond.behaviours.types import BehaviourEvent
from bond.conversation.conversation import Conversation
from bond.conversation.types import ToolCall, UsageInfo
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse


class ErrorEvent(BehaviourEvent):
    def __init__(self, *, error: Exception, critical: bool):
        self._error = error
        self.critical = critical

    type: Literal["error"] = "error"
    _error: Exception = PrivateAttr()
    critical: bool

    def error(self) -> Exception:
        return self._error


class StopEvent(BehaviourEvent):
    type: Literal["stop"] = "stop"


class NotifyEvent(BehaviourEvent):
    type: Literal["notify"] = "notify"
    message: str


class FullResponseEvent(BehaviourEvent):
    type: Literal["full_response"] = "full_response"
    author: str
    role: str
    response: CompletionResponse


class ResponseStartEvent(BehaviourEvent):
    type: Literal["response_start"] = "response_start"
    author: str
    role: str


class ResponseEndEvent(BehaviourEvent):
    type: Literal["response_end"] = "response_end"
    usage: UsageInfo | None


class WaitingForInputEvent(BehaviourEvent):
    type: Literal["waiting_for_input"] = "waiting_for_input"


class AppendMessageChunkEvent(BehaviourEvent):
    type: Literal["append_message_chunk"] = "append_message_chunk"
    chunk: CompletionChunk


class RequestConfirmationEvent(BehaviourEvent):
    def __init__(self, *, request: str, result: Future[bool]):
        self.request = request
        self._result = result

    type: Literal["request_confirmation"] = "request_confirmation"
    request: str
    _result: Future[bool] = PrivateAttr()

    def result(self):
        return self._result


class CancelRequestConfirmationEvent(BehaviourEvent):
    type: Literal["cancel_request_confirmation"] = "cancel_request_confirmation"


class CommandResponseEvent(BehaviourEvent):
    type: Literal["command_response"] = "command_response"


class CallToolEvent(BehaviourEvent):
    type: Literal["call_tool"] = "call_tool"
    call: ToolCall


class ToolReturnEvent(BehaviourEvent):
    type: Literal["tool_return"] = "tool_return"
    result: str


class ChangePersonaEvent(BehaviourEvent):
    type: Literal["change_persona"] = "change_persona"
    name: str
    provider: str


class ClearChatEvent(BehaviourEvent):
    type: Literal["clear_chat"] = "clear_chat"


class RestoreConversationEvent(BehaviourEvent):
    type: Literal["restore_conversation"] = "restore_conversation"
    conversation: Conversation
