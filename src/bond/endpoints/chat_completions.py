import json
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, field_serializer, field_validator

from bond.endpoints.model_options import ModelOptions


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
    finish_reason: FinishReason
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
        options: ChatCompletionArgType,
        max_retries: int = 3,
    ) -> CompletionResponse: ...
    def stream_chat_completions(
        self,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        callback: ChatCompletionStreamCallback,
        options: ChatCompletionArgType,
        max_retries: int = 3,
    ) -> CompletionResponse: ...
    def supports_streaming(self) -> bool: ...
