from rich.text import Text
from textual.containers import Container, ScrollableContainer, Vertical
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, TextArea

_THINK_COLOR = "grey"


class StatusBar(Static):
    model = reactive("<unknown>")
    provider = reactive("<unknown>")
    status = reactive("Idle")
    context_length = reactive(0)

    def render(self) -> Text:
        return Text.assemble(
            ("Model: ", "bold"),
            f"{self.model}  ",
            ("Provider: ", "bold"),
            f"{self.provider}  ",
            ("Status: ", "bold"),
            f"{self.status}  ",
            ("Context: ", "bold"),
            f"{self.context_length}",
        )


class InputBar(Container):
    def compose(self):
        self.input_field = MultiLineInput(
            placeholder="Type a message or :command",
            id="message-input",
        )
        yield self.input_field

    def focus(self, *args, **kwargs):
        self.input_field.focus(*args, **kwargs)


class FoldableBlock(Static):
    expanded = reactive(False)

    def __init__(self, title: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.content_str = content

    def on_click(self) -> None:
        self.expanded = not self.expanded
        self.refresh(layout=True)

    def append(self, delta: str):
        self.content_str += delta
        if self.expanded:
            self.refresh(layout=True)

    def render(self) -> Text:
        text = Text()

        arrow = "▼" if self.expanded else "▶"
        text.append(f"{arrow} {self.title}", style="bold")

        if self.expanded:
            text.append("\n")
            text.append(self.content_str)

        return text


class TextBlock(Static):

    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.text = text

    def append(self, delta: str):
        self.text += delta
        self.refresh(layout=True)

    def render(self) -> Text:
        t = Text()
        t.append(self.text)
        return t


class ThinkBlock(FoldableBlock):
    def __init__(self, text: str, **kwargs):
        super().__init__("Thinking", text, **kwargs)


class ToolResultBlock(FoldableBlock):
    def __init__(self, text: str, name: str | None = None, **kwargs):
        super().__init__(name or "Tool Call", text, **kwargs)


class ChatMessage(Vertical):
    header: Static

    @classmethod
    def create_user_msg(cls, author: str, text: str) -> "ChatMessage":
        msg = ChatMessage(author, "user")
        msg.add_text_block(text)
        return msg

    @classmethod
    def create_command_msg(cls, text: str) -> "ChatMessage":
        msg = ChatMessage("System", "system")
        msg.add_text_block(text)
        return msg

    def __init__(self, author: str, role: str, **kwargs):
        super().__init__(**kwargs)

        self.author = author
        self.role = role
        self.elements: list[Static] = []
        self.add_class(self.role)

    def compose(self):
        border_color = self.styles.border_left[1].hex
        self.header = Static(f"[b][{border_color}]{self.author}[/{border_color}][/b]:")
        yield self.header
        for element in self.elements:
            yield element

    def add_text_block(self, text: str) -> TextBlock:
        block = TextBlock(text)
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
        if len(self.elements) == 0 or not isinstance(self.elements[-1], TextBlock):
            self.add_text_block(text)
        else:
            self.elements[-1].append(text)

    def append_thinking(self, text: str):
        if len(self.elements) == 0 or not isinstance(self.elements[-1], ThinkBlock):
            self.add_think_block(text)
        else:
            self.elements[-1].append(text)

    def append_tool_result(self, text: str, name: str | None = None):
        self.add_tool_result_block(text, name)


class ChatMessage2(Static):
    think_str = reactive("")
    content_str = reactive("")

    def __init__(self, author: str, content: str, think: str, role: str, **kwargs):
        super().__init__(**kwargs)
        self.author = author
        self.content_str = content
        self.think_str = think
        self.role = role
        self.add_class(self.role)

    def append_content(self, content_delta: str | None, think_delta: str | None):
        if content_delta is not None:
            self.content_str = self.content_str + content_delta
        if think_delta is not None:
            self.think_str = self.think_str + think_delta
        self.update(self.render())

    def render(self) -> Text:
        border_color = self.styles.border_left[1].hex

        text = Text()
        text.append(f"{self.author}:\n", style=f"bold {border_color}")
        if self.think_str != "":
            text.append(self.think_str + "\n\n", style=_THINK_COLOR)
        text.append(self.content_str)
        return text


class ChatLog(ScrollableContainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages: list[ChatMessage] = []

    def add_message(self, message: ChatMessage):
        self.mount(message)


class MultiLineInput(TextArea):
    def on_key(self, event: Key) -> None:
        if event.key == "shift+enter":
            self.insert("\n", self.cursor_location)
            self.move_cursor_relative(rows=1)
        elif event.key == "enter":
            self.on_submit()
            self.clear()
            event.prevent_default()

    def on_submit(self):
        self.post_message(self.Submitted(self.text))
        pass

    class Submitted(Message):
        """Event emitted when Enter is pressed without Ctrl."""

        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()
