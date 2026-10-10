import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator


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


class BaseConversationMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserConversationMessage(BaseConversationMessage):
    message: UserMessage
    name: str

    def render(self) -> UserMessage:
        return self.message


class AssistantConversationMessage(BaseConversationMessage):
    message: AssistantMessage
    name: str
    condensed_thoughts: str | None = None

    # TODO: do we need this? Maybe we just generate the thoughts before creating this object
    def condense_thought(self, condensate: str):
        if self.condensed_thoughts is not None:
            raise RuntimeError("Tried to condense already condensed thoughts")
        self.condensed_thoughts = condensate

    def render(self, condense: bool) -> AssistantMessage:
        if self.message.content is None:
            return self.message
        if self.condensed_thoughts is None and not condense:
            return self.message
        non_thoughts: list[AssistantMessageChunk] = [
            chunk for chunk in self.message.content if not isinstance(chunk, ThinkChunk)
        ]
        if condense:
            return AssistantMessage(
                tool_calls=self.message.tool_calls, content=non_thoughts
            )
        assert self.condensed_thoughts is not None  # follows logically
        content = [
            ThinkChunk(thinking=[TextChunk(text=self.condensed_thoughts)])
        ] + non_thoughts
        return AssistantMessage(tool_calls=self.message.tool_calls, content=content)


class ToolConversationMessage(BaseConversationMessage):
    message: ToolMessage
    name: str
    tool_call_parameters: dict[str, Any] | None = None
    tool_call_summary: str | None = None

    def render(self, condense: bool) -> ToolMessage:
        if not condense:
            return self.message
        return ToolMessage(
            name=self.message.name,
            tool_call_id=self.message.tool_call_id,
            content=[
                TextChunk(text=self.tool_call_summary or "<tool output truncated>")
            ],
        )


ConversationMessage = (
    UserConversationMessage | AssistantConversationMessage | ToolConversationMessage
)


class Turn(BaseModel):
    """
    A single agentic turn: triggers like user input or tool responses
    followed up by an assistant message.
    """

    turn_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_messages: list[ToolConversationMessage] | None = None
    user_message: UserConversationMessage | None = None
    assistant_response: AssistantConversationMessage
    usage: UsageInfo | None = None
    condensed: bool = False

    def model_post_init(self, context: Any, /) -> None:
        if self.user_message is None and self.tool_messages is None:
            raise ValueError("A turn must have a user message or tool responses")

    @property
    def completed_at(self) -> datetime:
        return self.assistant_response.timestamp

    @property
    def ends_run(self) -> bool:
        return self.assistant_response.message.tool_calls is None

    @property
    def is_user_triggered(self) -> bool:
        """
        Determine whether the turn was triggered by the user.
        """
        return self.user_message is not None

    def condense(self) -> None:
        self.condensed = True

    def render(self) -> list[Message]:
        messages: list[Message] = []
        if self.tool_messages is not None:
            messages = [msg.render(self.condensed) for msg in self.tool_messages]
        if self.user_message is not None:
            messages.append(self.user_message.render())
        messages.append(self.assistant_response.render(self.condensed))
        return messages

    def flatten(self) -> list[ConversationMessage]:
        messages: list[ConversationMessage] = []
        if self.tool_messages is not None:
            messages = list(self.tool_messages)
        if self.user_message is not None:
            messages.append(self.user_message)
        messages.append(self.assistant_response)
        return messages


class Episode(BaseModel):
    """A group of turns that share common context.

    ``prefix_summary`` is a summary of all episodes *before* this one —
    i.e. the context that was available when this episode's turns were active.
    ``episode_summary`` is a summary of this episode's turns.

    An episode is *finished* when ``episode_summary`` is set. The last episode
    in a conversation is always unfinished.
    """

    episode_id: str = Field(default_factory=lambda: str(uuid4()))
    prefix_summary: str | None = None
    episode_summary: str | None = None
    turns: list[Turn] = []
    summarized_at: datetime | None = None

    @property
    def is_finished(self) -> bool:
        return self.episode_summary is not None

    def render(self) -> list[Message]:
        return [msg for turn in self.turns for msg in turn.render()]

    def flatten(self) -> list[ConversationMessage]:
        return [msg for turn in self.turns for msg in turn.flatten()]
