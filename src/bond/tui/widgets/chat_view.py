from typing import Literal

from textual.containers import Container

from bond.conversation.conversation import Conversation, ConversationMessage
from bond.conversation.types import (
    AssistantMessage,
    TextChunk,
    ThinkChunk,
    ToolMessage,
    UserMessage,
)
from bond.tui.widgets.chat_log import ChatLog, ChatMessage
from bond.tui.widgets.input_bar import InputBar
from bond.tui.widgets.status_bar import StatusBar


class ChatView(Container):
    def __init__(self):
        super().__init__()
        self.status_bar = StatusBar(
            status="<unknown>",
            persona="<unknown>",
            provider="<unknown>",
            context_length=0,
        )
        self.chat_log = ChatLog()
        self.input_bar = InputBar()

    def compose(self):
        yield self.status_bar
        yield self.chat_log
        yield self.input_bar

    def focus(self, scroll_visible: bool = True):
        self.input_bar.focus()

    # Control

    async def clear(self):
        await self.chat_log.clear()
        self.input_bar.clear()

    def add_conversation_message(self, message: ConversationMessage):
        if (
            self.last_message is not None
            and message.message.role == self.last_message.role
        ):
            _append_chunks(self.last_message, message.message.content or [])
        elif isinstance(message.message, ToolMessage):
            if self.last_message is None or self.last_message.role != "assistant":
                msg = ChatMessage("<unknown>", "assistant")
                self.chat_log.add_message(msg)
            else:
                msg = self.last_message
            msg.add_tool_result_block(
                "".join(
                    chunk.text
                    for chunk in message.message.content or []
                    if isinstance(chunk, TextChunk)
                )
            )
        elif isinstance(message.message, UserMessage) or isinstance(
            message.message, AssistantMessage
        ):
            msg = ChatMessage(message.author or "<unknown>", message.message.role)
            _append_chunks(msg, message.message.content or [])
            self.chat_log.add_message(msg)

    @property
    def last_message(self) -> ChatMessage | None:
        messages = self.chat_log.messages
        if len(messages) == 0:
            return None
        return messages[-1]

    async def sync(self, conversation: Conversation):
        await self.chat_log.clear()
        for message in conversation.history:
            self.add_conversation_message(message)
        self.status_bar.set_usage(conversation.current_usage)
        self.chat_log.scroll_end(animate=False)

    def ensure_current_author(
        self, role: Literal["user", "system", "assistant"], author: str | None
    ):
        if self.last_message is None or (
            author is not None and self.last_message.author != author
        ):
            self.chat_log.add_message(ChatMessage(author or "<unknown>", role))

    # Event Handling

    def on_key(self):
        pass


def _append_chunks(msg: ChatMessage, chunks: list):
    for chunk in chunks:
        if isinstance(chunk, TextChunk):
            msg.append_text(chunk.text)
        if isinstance(chunk, ThinkChunk):
            msg.append_text(
                "".join(c.text for c in chunk.thinking if isinstance(c, TextChunk))
            )
