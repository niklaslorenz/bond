import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, field_validator
from requests import Response

from bond.endpoints.model_options import ModelOptions
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
        tools: list[dict[str, Any]],
        **additional_fields,
    ) -> Response: ...


class ChatCompletionsWrapper[ModelArgumentType: ModelOptions]:
    provider: ChatCompletionsProvider

    def __init__(
        self,
        provider: ChatCompletionsProvider,
        general_arguments: ModelArgumentType | None = None,
        model_specific_arguments: dict[str, ModelArgumentType] = {},
        arguments_type: type[ModelArgumentType] | None = None,
    ):
        self.provider = provider
        self.general_arguments = (
            general_arguments.parse() if general_arguments is not None else {}
        )
        self.model_specific_arguments = {
            name: model.parse() for name, model in model_specific_arguments.items()
        }
        self.arguments_type = arguments_type

    def chat_completion(
        self,
        model: str,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        additional_arguments: ModelArgumentType | dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> ChatCompletionResponse:
        additional_fields = self.general_arguments.copy()
        for k, v in (self.model_specific_arguments.get(model) or {}).items():
            additional_fields[k] = v
        if additional_arguments is not None:
            if self.arguments_type is None:
                raise ValueError(
                    "Passing a raw value dictionary to chat_completion is not allowed, when the arguments type of the wrapper is not set."
                )
            args: ModelArgumentType = (
                self.arguments_type.model_validate(additional_arguments)
                if isinstance(additional_arguments, dict)
                else additional_arguments
            )
            for k, v in args.parse().items():
                additional_fields[k] = v
        response = http_retry_loop(
            lambda: self.provider.chat_completion(
                model, messages, tools if tools is not None else [], **additional_fields
            ),
            max_retries,
        )
        return ChatCompletionResponse.model_validate(response.json())
