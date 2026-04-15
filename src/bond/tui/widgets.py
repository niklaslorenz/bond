from typing import Callable, Protocol

from rich.markdown import Markdown
from rich.text import Text
from textual.containers import (Container, Horizontal, ScrollableContainer,
                                Vertical)
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Static, TextArea

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


class IPopup(Protocol):
    def set_overlay(self, overlay: "OverlayContainer"): ...


class ConfirmationPopup(Vertical):

    overlay: "OverlayContainer | None" = None

    def __init__(
        self,
        request: str,
        on_accept: Callable[[], None] | None = None,
        on_deny: Callable[[], None] | None = None,
        close_on_confirm: bool = True,
    ):
        super().__init__()
        self.on_accept = on_accept
        self.on_deny = on_deny
        self.accept_button = Button(
            "Accept", variant="success", id="confirmation-request-accept-button"
        )
        self.deny_button = Button(
            "Deny", variant="error", id="confirmation-request-deny-button"
        )
        self.close_on_confirm = close_on_confirm

        self.request_field = Static(request)

    def set_overlay(self, overlay: "OverlayContainer"):
        self.overlay = overlay

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirmation-request-accept-button":
            self.post_message(ConfirmationPopup.Accepted(self))
            if self.on_accept:
                self.on_accept()
            if self.close_on_confirm and self.overlay is not None:
                self.overlay.remove()

        if event.button.id == "confirmation-request-deny-button":
            self.post_message(ConfirmationPopup.Denied(self))
            if self.on_deny:
                self.on_deny()
            if self.close_on_confirm and self.overlay is not None:
                self.overlay.remove()

    def compose(self):
        with ScrollableContainer():
            yield self.request_field
        with Horizontal(classes="button-bar"):
            yield self.deny_button
            yield self.accept_button

    class Accepted(Message):
        def __init__(self, popup: "ConfirmationPopup"):
            super().__init__()
            self.popup = popup

    class Denied(Message):
        def __init__(self, popup: "ConfirmationPopup"):
            super().__init__()
            self.popup = popup


class ConversationSelectorPopup(Vertical):

    overlay: "OverlayContainer | None" = None

    def __init__(
        self,
        conversations: list[str],
        on_select: Callable[[str], None],
        on_cancel: Callable[[], None],
    ):
        super().__init__()
        self.conversations = conversations
        self.on_select = on_select
        self.on_cancel = on_cancel
        self.cancel_button = Button(
            "Cancel",
            variant="error",
            id="conversation-selector-cancel-button",
        )
        self._option_map: dict[str, str] = {}

    def set_overlay(self, overlay: "OverlayContainer"):
        self.overlay = overlay

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "conversation-selector-cancel-button":
            if self.on_cancel:
                self.on_cancel()
            if self.overlay is not None:
                self.overlay.remove()
            return

        if event.button.id is None:
            return
        name = self._option_map.get(event.button.id)
        if name:
            if self.on_select:
                self.on_select(name)
            if self.overlay is not None:
                self.overlay.remove()

    def compose(self):
        yield Static("Load Conversation", classes="conversation-selector-title")
        with ScrollableContainer(classes="conversation-selector-list"):
            if len(self.conversations) == 0:
                yield Static("No saved conversations yet.", classes="empty-state")
            for index, name in enumerate(self.conversations):
                btn_id = f"conversation-selector-option-{index}"
                button = Button(
                    name,
                    id=btn_id,
                    variant="primary",
                    classes="conversation-selector-option",
                )
                self._option_map[btn_id] = name
                yield button
        with Horizontal(classes="button-bar"):
            yield self.cancel_button


class OverlayContainer(Container):

    def __init__(
        self,
        popup: IPopup,
    ):
        super().__init__()
        self.popup = popup
        popup.set_overlay(self)

    def compose(self):
        yield self.popup
