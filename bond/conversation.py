from pydantic import BaseModel

from bond.endpoints.chat_completions import (Message, SystemMessage, TextChunk,
                                             ToolCall, ToolMessage,
                                             UserMessage)

# TODO: Add a size attribute to the history objects and update them
# whenever a prompt returns a usage report.
# Use this to prune the context window


class Conversation(BaseModel):
    history: list[Message] = []
    system_message: SystemMessage | None

    @classmethod
    def create(cls, system_prompt: str | None = None) -> "Conversation":
        return Conversation(
            system_message=(
                SystemMessage(content=[TextChunk(text=system_prompt)])
                if system_prompt is not None
                else None
            )
        )

    def add_user_message(self, content: str):
        self.history.append(UserMessage(content=[TextChunk(text=content)]))

    def add_tool_str_response(self, tool_call: ToolCall, tool_output: str):
        self.history.append(
            ToolMessage(
                name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=[TextChunk(text=tool_output)],
            ),
        )

    def get_messages(self) -> list[Message]:
        messages: list[Message] = []
        if self.system_message is not None:
            messages.append(self.system_message)
        messages += self.history
        return messages

    def add_message(self, message: Message):
        self.history.append(message)
