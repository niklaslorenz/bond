import functools
import json
from collections import defaultdict
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, field_serializer, field_validator

from bond.endpoints.model_options import ModelOptions
from bond.tools.tool import Tool


class TextChunk(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ReferenceChunk(BaseModel):
    type: Literal["reference"]
    reference_ids: list[int]


class ToolReferenceChunk(BaseModel):
    type: Literal["tool_reference"] = "tool_reference"
    description: str | None = None
    favicon: str | None = None
    title: str
    tool: str
    url: str | None = None


class ThinkChunk(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: list[TextChunk | ToolReferenceChunk | ReferenceChunk]


AssistantMessageChunk = TextChunk | ReferenceChunk | ThinkChunk
UserMessageChunk = TextChunk | ReferenceChunk | ThinkChunk
SystemMessageChunk = ThinkChunk | TextChunk
ToolMessageChunk = TextChunk | ReferenceChunk | ThinkChunk


class FunctionCall(BaseModel):
    name: str
    arguments: dict[str, Any]

    # The mistral api defines arguments to be a json string
    # so the validator and serializer convert it to/from the dictionary
    @field_validator("arguments", mode="before")
    def arguments_string_to_dict(cls, val):
        if isinstance(val, str):
            return json.loads(val)
        return val

    @field_serializer("arguments", mode="plain", when_used="always")
    def arguments_to_string(self, arguments: dict[str, Any]) -> str:
        return json.dumps(arguments)


class ToolCall(BaseModel):
    type: Literal["function"] = "function"
    id: str | None = None
    function: FunctionCall


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    tool_calls: list[ToolCall] | None = None
    content: list[AssistantMessageChunk] | None = None

    @field_validator("content", mode="before")
    def content_string_to_list(cls, val):
        if isinstance(val, str):
            return [TextChunk(text=val)]
        return val


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: list[UserMessageChunk] | None = None

    @classmethod
    def create(cls, msg: str) -> "UserMessage":
        return UserMessage(content=[TextChunk(text=msg)])


class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: list[SystemMessageChunk]

    @field_validator("content", mode="before")
    def content_string_to_list(cls, val):
        if isinstance(val, str):
            return [TextChunk(text=val)]
        return val

    @classmethod
    def create(cls, msg: str) -> "SystemMessage":
        return SystemMessage(content=[TextChunk(text=msg)])


class ToolMessage(BaseModel):
    role: Literal["tool"] = "tool"
    name: str | None = None
    tool_call_id: str | None = None
    content: list[ToolMessageChunk] | None = None


Message = AssistantMessage | UserMessage | SystemMessage | ToolMessage


class UsageInfo(BaseModel):
    completion_tokens: int
    prompt_audio_seconds: int | None = None
    prompt_tokens: int
    total_tokens: int


FinishReason = Literal["stop", "length", "model_length", "error", "tool_calls"]


class CompletionChoice(BaseModel):
    finish_reason: FinishReason
    message: AssistantMessage


class CompletionResponse(BaseModel):
    choices: list[CompletionChoice]
    created: int
    id: str
    model: str
    object: Literal["chat.completion"] = "chat.completion"
    usage: UsageInfo


class DeltaMessage(BaseModel):
    content: AssistantMessageChunk | None = None
    role: Literal["assistant"] | None = None
    tool_calls: list[ToolCall] | None = None

    @field_validator("content", mode="before")
    def content_string_to_chunk(cls, val):
        if isinstance(val, str):
            return TextChunk(text=val)
        return val


class CompletionResponseStreamChoice(BaseModel):
    finish_reason: FinishReason | None = None
    delta: DeltaMessage
    index: int


class CompletionChunk(BaseModel):
    choices: list[CompletionResponseStreamChoice]
    created: int
    id: str
    model: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    usage: UsageInfo | None = None


ChatCompletionStreamCallback = Callable[[CompletionChunk], None]


class ChatCompletionsEndpoint[ChatCompletionArgType: ModelOptions](Protocol):
    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        options: ChatCompletionArgType | None = None,
        max_retries: int = 3,
    ) -> CompletionResponse: ...
    def stream_chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        options: ChatCompletionArgType | None = None,
        max_retries: int = 3,
    ) -> CompletionResponse: ...
    def supports_streaming(self) -> bool: ...


def build_response(chunks: list[CompletionChunk]) -> CompletionResponse:
    if len(chunks) == 0:
        raise RuntimeError("Empty Response")

    tool_calls: dict[int, list[ToolCall]] = defaultdict(list)
    finish_reasons: dict[int, FinishReason] = {}
    content: dict[int, list[AssistantMessageChunk]] = defaultdict(list)

    usage_info: UsageInfo | None = None

    for chunk in chunks:
        if chunk.usage is not None:
            if usage_info is not None:
                raise RuntimeError("Received duplicate usage info")
            usage_info = chunk.usage
        for choice in chunk.choices:
            idx = choice.index
            if choice.finish_reason is not None:
                if idx in finish_reasons:
                    raise RuntimeError("Received duplicate finish reason")
                finish_reasons[idx] = choice.finish_reason
            if choice.delta.tool_calls is not None:
                tool_calls[idx] += choice.delta.tool_calls
            if choice.delta.content is not None:
                content[idx].append(choice.delta.content)

    # Fold content
    def absorb_chunk[T](acc: list[T], content_chunk: T):
        if len(acc) == 0:
            acc.append(content_chunk)
            return acc
        last = acc[-1]

        if isinstance(last, TextChunk) and isinstance(content_chunk, TextChunk):
            last.text += content_chunk.text
            return acc

        if isinstance(last, ThinkChunk) and isinstance(content_chunk, ThinkChunk):
            if len(last.thinking) == 0:
                last.thinking = content_chunk.thinking
                return acc
            last.thinking = last.thinking[:-1] + functools.reduce(
                absorb_chunk, content_chunk.thinking, [last.thinking[-1]]
            )
            return acc

        if isinstance(last, ReferenceChunk) and isinstance(
            content_chunk, ReferenceChunk
        ):
            last.reference_ids += content_chunk.reference_ids
            return acc

        # No need to merge ToolReferenceChunks

        acc.append(content_chunk)
        return acc

    final_content: list[tuple[int, list[AssistantMessageChunk]]] = [
        (idx, functools.reduce(absorb_chunk, content_chunks, []))
        for idx, content_chunks in content.items()
    ]
    final_content.sort(key=lambda x: x[0])
    choices = [
        CompletionChoice(
            finish_reason=finish_reasons[idx],
            message=AssistantMessage(
                tool_calls=tool_calls[idx], content=content_chunks
            ),
        )
        for idx, content_chunks in final_content
    ]

    if usage_info is None:
        raise RuntimeError("No usage info received")

    return CompletionResponse(
        choices=choices,
        created=chunks[0].created,
        id=chunks[0].id,
        model=chunks[0].model,
        usage=usage_info,
    )
