import asyncio
import logging
from typing import Literal

from rich.markdown import Markdown
from rich.text import Text
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Static

logger = logging.getLogger(__name__)


class FoldableBlock(Static):
    expanded = reactive(False)

    def __init__(self, title: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.text = content

    def on_click(self) -> None:
        self.expanded = not self.expanded
        self.refresh(layout=True)

    def append(self, delta: str):
        self.text += delta
        if self.expanded:
            self.refresh(layout=True)

    def render(self) -> Text:
        text = Text()

        arrow = "▼" if self.expanded else "▶"
        text.append(f"{arrow} {self.title}", style="bold")

        if self.expanded:
            text.append("\n")
            text.append(self.text)

        return text


class MarkdownBlock(Static):
    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.text = text

    def append(self, delta: str):
        self.text += delta
        self.refresh(layout=True)

    def render(self) -> Markdown:
        return Markdown(self.text)


class ThinkBlock(FoldableBlock):
    def __init__(self, text: str, **kwargs):
        super().__init__("Thinking", text, **kwargs)


class ToolResultBlock(FoldableBlock):
    def __init__(self, text: str, name: str | None = None, **kwargs):
        super().__init__(name or "Tool Call", text, **kwargs)


class ChatMessage(Vertical):

    def __init__(
        self, author: str, role: Literal["user", "system", "assistant"], **kwargs
    ):
        super().__init__(**kwargs)
        self.author = author
        self.role = role
        border_color = self.styles.border_left[1].hex
        self.header = Static(f"[b][{border_color}]{self.author}[/{border_color}][/b]:")
        self.elements: list[Static] = []
        self.add_class(self.role)

    def compose(self):
        yield self.header
        for element in self.elements:
            yield element

    def add_markdown_block(self, text: str) -> MarkdownBlock:
        block = MarkdownBlock(text)
        self.elements.append(block)
        if self.is_mounted:
            self.mount(block)
        return block

    def add_think_block(self, text: str) -> ThinkBlock:
        block = ThinkBlock(text)
        self.elements.append(block)
        if self.is_mounted:
            self.mount(block)
        return block

    def add_tool_result_block(
        self, text: str, name: str | None = None
    ) -> ToolResultBlock:
        block = ToolResultBlock(text, name)
        self.elements.append(block)
        if self.is_mounted:
            self.mount(block)
        return block

    def append_text(self, text: str):
        if len(self.elements) == 0 or not isinstance(self.elements[-1], MarkdownBlock):
            self.add_markdown_block(text)
        else:
            self.elements[-1].append(text)

    def append_thinking(self, text: str):
        if len(self.elements) == 0 or not isinstance(self.elements[-1], ThinkBlock):
            self.add_think_block(text)
        else:
            self.elements[-1].append(text)

    def on_mount(self):
        for element in self.elements:
            if not element.is_mounted:
                self.mount(element)


class ChatLog(ScrollableContainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages: list[ChatMessage] = []

    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        if self.is_mounted:
            self.mount(message)

    async def on_mount(self):
        futures = []
        for msg in self.messages:
            if not msg.is_mounted:
                futures.append(self.mount(msg))
        await asyncio.gather(*futures)

    async def clear(self):
        if self.is_mounted:
            futures = [msg.remove() for msg in self.messages]
            await asyncio.gather(*futures)
        self.messages.clear()
