import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator
from typing_extensions import deprecated


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


class ConversationMetadata(BaseModel):
    mistral_cache_key: str | None = None


class ConversationMessage(BaseModel):
    message: Message
    author: str | None = None
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    usage: UsageInfo | None = None

    @classmethod
    def create_system_message(
        cls, msg: str, system_name: str = "System"
    ) -> "ConversationMessage":
        return ConversationMessage(
            author=system_name, message=SystemMessage(content=[TextChunk(text=msg)])
        )

    @classmethod
    def create_user_message(
        cls, msg: str, user_name: str = "User"
    ) -> "ConversationMessage":
        return ConversationMessage(
            author=user_name, message=UserMessage(content=[TextChunk(text=msg)])
        )

    @classmethod
    def create_tool_response_message(
        cls, response: str, tool_call: ToolCall, tool_name: str | None = None
    ) -> "ConversationMessage":
        return ConversationMessage(
            author=tool_name or tool_call.function.name,
            message=ToolMessage(
                name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=[TextChunk(text=response)],
            ),
        )


# DEPRECATED: Only used by old std_event_handler and std_command_handler
@deprecated(
    "Ignores structure of think and text chunks and deprecated without replacement"
)
def parse_chunks_content(chunks: list) -> tuple[str | None, str | None]:
    text = []
    think = []
    for chunk in chunks:
        if isinstance(chunk, TextChunk):
            text.append(chunk.text)
        elif isinstance(chunk, ThinkChunk):
            for think_chunk in chunk.thinking:
                if isinstance(think_chunk, TextChunk):
                    think.append(think_chunk.text)
    return (
        "".join(text) if len(text) > 0 else None,
        "".join(think) if len(think) > 0 else None,
    )
