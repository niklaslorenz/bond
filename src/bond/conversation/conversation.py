from dataclasses import field
from pathlib import Path

from pydantic import BaseModel

from bond.conversation.types import (ConversationMetadata, Message,
                                     SystemMessage, TextChunk, ToolCall,
                                     ToolMessage, UserMessage)

# TODO: Add a size attribute to the history objects and update them
# whenever a prompt returns a usage report.
# Use this to prune the context window


class ConversationMessage(BaseModel):
    message: Message
    author: str | None = None

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


class Conversation(BaseModel):
    history: list[ConversationMessage] = []
    name: str | None = None
    current_persona: str | None = None
    metadata: ConversationMetadata = field(default_factory=ConversationMetadata)
    summary: ToolMessage | None = None
    summary_index: int = 0

    def add_message(self, message: ConversationMessage):
        self.history.append(message)

    def get_summary_messages(self, keep: int) -> list[Message]:
        if keep <= 0:
            raise ValueError(f"keep must be a positive integer")
        recent_messages: list[Message] = [
            m.message
            for m in self.history[self.summary_index : -keep]
            if m.message.role != "system"
        ]
        return (
            recent_messages
            if self.summary is None
            else [self.summary] + recent_messages
        )

    def get_chat_completion_messages(self) -> list[Message]:
        recent_messages: list[Message] = [
            m.message
            for m in self.history[self.summary_index :]
            if m.message.role != "system"
        ]
        return (
            recent_messages
            if self.summary is None
            else [self.summary] + recent_messages
        )

    def num_unsummarized_messages(self) -> int:
        return len(self.history) - self.summary_index

    def update_summary(self, new_summary: ToolMessage, keep: int):
        if keep <= 0:
            raise ValueError(f"keep must be a positive integer")
        self.summary = new_summary
        self.summary_index = len(self.history) - keep

    def save_to_file(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path):
        return cls.model_validate_json(path.read_text())
