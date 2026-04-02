from concurrent.futures import CancelledError, Future
from pathlib import Path
from queue import Queue
from typing import Annotated, Callable, Literal, TextIO, Union

from pydantic import BaseModel, Field, PrivateAttr, TypeAdapter

from bond.behaviours.behaviour_signal import BehaviourSignal
from bond.conversation.conversation import Conversation
from bond.conversation.types import ToolCall, UsageInfo
from bond.endpoints.chat_completions import CompletionChunk, CompletionResponse

_CONFIRMATION_TIMEOUT = 30


class StreamStartEvent(BaseModel):
    type: Literal["stream_start"] = "stream_start"
    agent_name: str | None


class StreamEndEvent(BaseModel):
    type: Literal["stream_end"] = "stream_end"
    usage: UsageInfo | None


class StreamChunkEvent(BaseModel):
    type: Literal["stream_chunk"] = "stream_chunk"
    chunk: CompletionChunk


class CompletionResponseEvent(BaseModel):
    type: Literal["completion_response"] = "completion_response"
    response: CompletionResponse
    agent_name: str | None


class NotifyEvent(BaseModel):
    type: Literal["notify"] = "notify"
    message: str


class StopEvent(BaseModel):
    type: Literal["stop"] = "stop"


class ConfirmationRequestEvent(BaseModel):
    type: Literal["confirmation_request"] = "confirmation_request"
    prompt: str
    _value: Future[bool] = PrivateAttr()


class ToolCallResultEvent(BaseModel):
    type: Literal["tool_call_result"] = "tool_call_result"
    tool_call: ToolCall
    tool_return: str


class UpdatePersonaEvent(BaseModel):
    type: Literal["update_persona"] = "update_persona"
    persona_name: str
    provider_name: str


class BlockEvent(BaseModel):
    type: Literal["block"] = "block"


class ReleaseEvent(BaseModel):
    type: Literal["release"] = "release"


class ClearLogEvent(BaseModel):
    type: Literal["clear_log"] = "clear_log"


class SyncLogEvent(BaseModel):
    type: Literal["sync_log"] = "sync_log"
    conversation: Conversation
    message_count: int | None


BehaviourEvent = Annotated[
    Union[
        StreamStartEvent,
        StreamEndEvent,
        StreamChunkEvent,
        CompletionResponseEvent,
        NotifyEvent,
        StopEvent,
        ConfirmationRequestEvent,
        ToolCallResultEvent,
        UpdatePersonaEvent,
        BlockEvent,
        ClearLogEvent,
        SyncLogEvent,
        ReleaseEvent,
    ],
    Field(discriminator="type"),
]
BehaviourEventAdapter = TypeAdapter(BehaviourEvent)


class QueueAoe:
    def __init__(self, event_queue: Queue[BehaviourEvent]):
        self._queue = event_queue

    def start_streaming_response(self, name: str | None):
        self._queue.put(StreamStartEvent(agent_name=name))

    def end_streaming_response(self, usage: UsageInfo | None):
        self._queue.put(StreamEndEvent(usage=usage))

    def handle_response_chunk(self, chunk: CompletionChunk):
        self._queue.put(StreamChunkEvent(chunk=chunk))

    def handle_response(self, response: CompletionResponse, name: str | None):
        self._queue.put(CompletionResponseEvent(response=response, agent_name=name))


class QueueSignalReceiver:
    def __init__(self, queue: Queue[BehaviourSignal]):
        self._queue = queue

    def __call__(self) -> BehaviourSignal:
        return self._queue.get()


class QueueNotifier:
    def __init__(self, queue: Queue[BehaviourEvent]):
        self._queue = queue

    def __call__(self, msg: str):
        self._queue.put(NotifyEvent(message=msg))


class QueueToolEnvironment:
    def __init__(
        self,
        work_dir: Path | Callable[[], Path] | None,
        event_queue: Queue[BehaviourEvent],
    ):
        self._work_dir = work_dir
        self._event_queue = event_queue

    def ask_confirmation(self, prompt: str) -> bool:
        future: Future[bool] = Future()
        request = ConfirmationRequestEvent(prompt=prompt)
        request._value = future
        self._event_queue.put(request)
        try:
            return future.result(timeout=_CONFIRMATION_TIMEOUT)
        except CancelledError | TimeoutError:
            return False

    def is_interactive(self) -> bool:
        return True

    def get_work_dir(self) -> Path | None:
        if self._work_dir is None:
            return None
        if isinstance(self._work_dir, Path):
            return self._work_dir
        return self._work_dir()

    def handle_result(self, tool_call: ToolCall, result: str):
        self._event_queue.put(
            ToolCallResultEvent(tool_call=tool_call, tool_return=result)
        )

    def supports_stdout(self) -> bool:
        # TODO: implement
        return False

    def handle_stdout(self, data: str, flush: bool = False):
        # TODO: implement
        pass

    def log_out(self) -> TextIO | None:
        # TODO: implement
        return None

    def log_err(self) -> TextIO | None:
        # TODO: implement
        return None
