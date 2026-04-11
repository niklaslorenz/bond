from rich.markdown import Markdown
from rich.text import Text
from textual.containers import Container, ScrollableContainer, Vertical
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, TextArea

_THINK_COLOR = "grey"


class StatusBar(Static):
    persona = reactive("<unknown>")
    provider = reactive("<unknown>")
    status = reactive("Idle")
    context_length = reactive(0)

    def __init__(
        self,
        persona: str = "<unknown>",
        provider: str = "<unknown>",
        status: str = "<unknown>",
        context_length: int = 0,
    ):
        super().__init__(id="status-bar")
        self.persona = persona
        self.provider = provider
        self.status = status
        self.context_length = context_length

    def render(self) -> Text:
        return Text.assemble(
            ("Persona: ", "bold"),
            f"{self.persona}  ",
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


class TextBlock(Static):

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

    def on_mount(self):
        for element in self.elements:
            if not element.is_mounted:
                self.mount(element)


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
            event.prevent_default()

    def on_submit(self):
        self.post_message(self.Submitted(self, self.text))
        pass

    class Submitted(Message):
        """Event emitted when Enter is pressed without Ctrl."""

        def __init__(self, input_field: "MultiLineInput", value: str) -> None:
            self.input_field = input_field
            self.value = value
            super().__init__()

        def clear_field(self):
            self.input_field.clear()
