import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, field_validator
from requests import Response

from bond.util import http_retry_loop


class FunctionParameter(BaseModel):
    type: Literal["string", "number", "integer", "boolean", "array", "object"]
    description: str


class FunctionParameters(BaseModel):
    type: Literal["object"]
    properties: dict[str, FunctionParameter]
    required: list[str] | None = None


class Function(BaseModel):
    name: str
    description: str = ""
    parameters: FunctionParameters
    strict: bool = False


class Tool(BaseModel):
    type: Literal["function"]
    function: Function


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


class FunctionCall(BaseModel):
    name: str
    arguments: dict[str, Any]

    @field_validator("arguments", mode="before")
    def arguments_string_to_dict(cls, val):
        if isinstance(val, str):
            return json.loads(val)
        return val


class ToolCall(BaseModel):
    type: Literal["function"] = "function"
    id: str | None = None
    function: FunctionCall


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    tool_calls: list[ToolCall] | None = None
    content: list[TextChunk | ReferenceChunk | ThinkChunk] | None = None

    @field_validator("content", mode="before")
    def content_string_to_list(cls, val):
        if isinstance(val, str):
            return [TextChunk(text=val)]
        return val


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: list[TextChunk | ReferenceChunk | ThinkChunk] | None = None

    @classmethod
    def create(cls, msg: str) -> "UserMessage":
        return UserMessage(content=[TextChunk(text=msg)])


class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: list[ThinkChunk | TextChunk]

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
    content: list[TextChunk | ReferenceChunk | ThinkChunk] | None = None


Message = AssistantMessage | UserMessage | SystemMessage | ToolMessage


class UsageInfo(BaseModel):
    completion_tokens: int
    prompt_audio_seconds: int | None = None
    prompt_tokens: int
    total_tokens: int


class ChatCompletionChoice(BaseModel):
    finish_reason: Literal["stop", "length", "model_length", "error", "tool_calls"]
    message: AssistantMessage


class ChatCompletionResponse(BaseModel):
    choices: list[ChatCompletionChoice]
    created: int
    id: str
    model: str
    object: Literal["chat.completion"] = "chat.completion"
    usage: UsageInfo


class ChatCompletionsProvider(Protocol):
    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **additional_fields,
    ) -> Response: ...


class ChatCompletionsWrapper:
    provider: ChatCompletionsProvider

    def __init__(self, provider: ChatCompletionsProvider):
        self.provider = provider

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        max_retries: int = 3,
        **additional_fields,
    ) -> ChatCompletionResponse:
        response = http_retry_loop(
            lambda: self.provider.chat_completion(
                model, messages, temperature, max_tokens, **additional_fields
            ),
            max_retries,
        )
        return ChatCompletionResponse.model_validate(response.json())
