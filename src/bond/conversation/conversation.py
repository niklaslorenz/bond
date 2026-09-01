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

    def add_message(self, message: ConversationMessage):
        self.history.append(message)

    def get_chat_completion_messages(
        self, skip_system_messages: bool = False
    ) -> list[Message]:
        return [
            m.message
            for m in self.history
            if m.message.role != "system" or not skip_system_messages
        ]

    def save_to_file(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path):
        return cls.model_validate_json(path.read_text())
