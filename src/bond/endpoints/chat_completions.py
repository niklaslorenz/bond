import functools
from collections import defaultdict
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, field_validator

from bond.conversation.types import (
    AssistantMessage,
    AssistantMessageChunk,
    ConversationMetadata,
    Message,
    ReferenceChunk,
    SystemMessage,
    TextChunk,
    ThinkChunk,
    ToolCall,
    UsageInfo,
)
from bond.tools.tool import Tool

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
    content: list[AssistantMessageChunk] | None = None
    role: Literal["assistant"] | None = None
    tool_calls: list[ToolCall] | None = None

    @field_validator("content", mode="before")
    def content_string_to_chunk(cls, val):
        if isinstance(val, str):
            return [TextChunk(text=val)] if val != "" else None
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


class ChatCompletionsEndpoint(Protocol):
    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        system_message: SystemMessage | None = None,
        options: dict[str, Any] | None = None,
        max_retries: int = 10,
        conversation_metadata: ConversationMetadata | None = None,
    ) -> CompletionResponse: ...
    def stream_chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        system_message: SystemMessage | None = None,
        options: dict[str, Any] | None = None,
        max_retries: int = 10,
        conversation_metadata: ConversationMetadata | None = None,
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
                for content_chunk in choice.delta.content:
                    content[idx].append(content_chunk)

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

    reduced_content: dict[int, list[AssistantMessageChunk]] = {
        idx: functools.reduce(absorb_chunk, content_chunks, [])
        for idx, content_chunks in content.items()
    }

    indices = list(set(reduced_content.keys()) | set(tool_calls.keys()))
    indices.sort()

    choices = [
        CompletionChoice(
            finish_reason=finish_reasons[idx],
            message=AssistantMessage(
                tool_calls=tool_calls[idx] if len(tool_calls[idx]) > 0 else None,
                content=reduced_content.get(idx),
            ),
        )
        for idx in indices
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
