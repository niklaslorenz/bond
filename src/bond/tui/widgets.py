import time
from difflib import SequenceMatcher
from typing import Callable

from rich.markdown import Markdown
from rich.text import Text
from textual.containers import (Container, Horizontal, ScrollableContainer,
                                Vertical)
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Input, Static, TextArea

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _get_tui_app(self):
        app = getattr(self, "app", None)
        if app is None:
            return None
        from .app import BondTui

        if not isinstance(app, BondTui):
            return None
        return app

    def _get_chat_log(self) -> ChatLog | None:
        app = self._get_tui_app()
        if app is None:
            return None
        return app.get_chat_log()

    def _get_chat_messages(self) -> list[ChatMessage]:
        app = self._get_tui_app()
        if app is None:
            return []
        return app.get_messages()

    def _find_current_message(
        self, messages: list[ChatMessage]
    ) -> tuple[int, ChatMessage, float, float] | None:
        log = self._get_chat_log()
        if log is None:
            return None
        scroll_y = log.scroll_y
        for idx, msg in enumerate(messages):
            region = msg.virtual_region
            height = max(region.height, 1)
            top = region.y
            bottom = top + height
            if bottom > scroll_y or idx == len(messages) - 1:
                return idx, msg, top, bottom
        return None

    def _last_visible_message(
        self,
        messages: list[ChatMessage],
        scroll_y: float,
        window_bottom: float,
    ) -> tuple[int, ChatMessage, float, float] | None:
        best = None
        for idx, msg in enumerate(messages):
            region = msg.virtual_region
            height = max(region.height, 1)
            top = region.y
            bottom = top + height
            if bottom <= scroll_y or top >= window_bottom:
                continue
            if best is None or bottom > best[3]:
                best = (idx, msg, top, bottom)
        if best is None and messages:
            msg = messages[-1]
            region = msg.virtual_region
            height = max(region.height, 1)
            top = region.y
            bottom = top + height
            best = (len(messages) - 1, msg, top, bottom)
        return best

    def _scroll_to_message_top(self, message: ChatMessage) -> None:
        log = self._get_chat_log()
        if log is None:
            return
        log.scroll_to_widget(
            message,
            animate=True,
            top=True,
            force=True,
            immediate=True,
        )

    def _scroll_to_message_bottom(self, message: ChatMessage) -> None:
        log = self._get_chat_log()
        if log is None:
            return
        window_height = log.scrollable_content_region.height
        region = message.virtual_region
        height = max(region.height, 1)
        top = region.y
        bottom = top + height
        if window_height <= 0:
            log.scroll_to_widget(
                message,
                animate=True,
                force=True,
                immediate=True,
            )
            return
        target_y = max(0, bottom - window_height)
        log.scroll_to(y=target_y, animate=True, immediate=True, force=True)

    def _scroll_to_message_top_or_previous(self) -> bool:
        messages = self._get_chat_messages()
        if not messages:
            return False
        data = self._find_current_message(messages)
        if data is None:
            return False
        idx, msg, top, _ = data
        log = self._get_chat_log()
        if log is None:
            return False
        if log.scroll_y <= top + 1 and idx > 0:
            target = messages[idx - 1]
        else:
            target = msg
        self._scroll_to_message_top(target)
        return True

    def _scroll_to_message_bottom_or_next(self) -> bool:
        messages = self._get_chat_messages()
        log = self._get_chat_log()
        if not messages or log is None:
            return False
        window_height = log.scrollable_content_region.height
        window_bottom = log.scroll_y + max(window_height, 0)
        data = self._last_visible_message(messages, log.scroll_y, window_bottom)
        if data is None:
            return False
        idx, msg, _, bottom = data
        target = msg
        if (
            window_height > 0
            and bottom <= window_bottom + 1
            and idx + 1 < len(messages)
        ):
            target = messages[idx + 1]
        self._scroll_to_message_bottom(target)
        return True

    def _scroll_chat_lines(self, delta: int) -> None:
        log = self._get_chat_log()
        if log is None:
            return
        log.scroll_relative(y=delta, animate=True, immediate=True)

    def _scroll_half_page(self, direction: int) -> None:
        log = self._get_chat_log()
        if log is None:
            return
        height = log.scrollable_content_region.height
        amount = max(1, height // 2) if height > 0 else 1
        log.scroll_relative(y=direction * amount, animate=True, immediate=True)

    def _handle_scroll_shortcut(self, key: str, event: Key) -> bool:
        handled = False
        if key == "ctrl+k":
            self._scroll_chat_lines(-5)
            handled = True
        elif key == "ctrl+j":
            self._scroll_chat_lines(5)
            handled = True
        elif key == "ctrl+u":
            self._scroll_half_page(-1)
            handled = True
        elif key == "ctrl+d":
            self._scroll_half_page(1)
            handled = True
        elif key == "ctrl+h":
            handled = self._scroll_to_message_top_or_previous()
        elif key == "ctrl+l":
            handled = self._scroll_to_message_bottom_or_next()
        else:
            return False
        if handled:
            event.stop()
        return handled

    def on_key(self, event: Key) -> None:
        key = event.key
        if self._handle_scroll_shortcut(key, event):
            return
        if key == "shift+enter":
            self.insert("\n", self.cursor_location)
            self.move_cursor_relative(rows=1)
        elif key == "enter":
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


class ConfirmationPopup(Vertical):
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

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirmation-request-accept-button":
            self.post_message(ConfirmationPopup.Accepted(self))
            if self.on_accept:
                self.on_accept()

        if event.button.id == "confirmation-request-deny-button":
            self.post_message(ConfirmationPopup.Denied(self))
            if self.on_deny:
                self.on_deny()

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


class ConversationSearchInput(Input):
    def __init__(
        self,
        owner: "ConversationSelectorPopup",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.owner = owner

    def on_key(self, event: Key) -> None:
        key = event.key
        if key in ("up", "ctrl+k"):
            event.stop()
            self.owner.move_selection(-1)
            return
        if key in ("down", "ctrl+j"):
            event.stop()
            self.owner.move_selection(1)
            return
        if key == "enter":
            event.stop()
            self.owner.select_current()
            return
        if key == "escape":
            event.stop()
            self.owner.cancel()
            return


class ConversationSelectorPopup(Vertical):
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
        self.list_container: ScrollableContainer = ScrollableContainer(
            classes="conversation-selector-list"
        )
        self.search_field = ConversationSearchInput(
            owner=self,
            placeholder="Search conversations",
            id="conversation-selector-search",
        )

        self._id_to_index: dict[str, int] = {}
        self._search_value: str = ""
        self._debounce_timer: Timer | None = None
        self._last_refresh = 0.0
        self._visible_buttons: list[Button] = []
        self._visible_conversations: list[str] = []
        self._selected_index: int = -1
        self._next_option_id = 0

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "conversation-selector-cancel-button":
            self.cancel()
            return

        if event.button.id is None:
            return
        idx = self._id_to_index.get(event.button.id)
        if idx is not None:
            self.select_current(idx)

    def compose(self):
        yield Static("Load Conversation", classes="conversation-selector-title")
        yield self.search_field
        yield self.list_container
        with Horizontal(classes="button-bar"):
            yield self.cancel_button

    def on_mount(self):
        self.refresh_conversation_list()
        self.search_field.focus()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id != "conversation-selector-search":
            return
        self._schedule_refresh(event.value)

    def on_key(self, event: Key):
        if event.key == "escape" or event.key == "ctrl+z":
            event.stop()
            self.cancel()
            return

    def cancel(self):
        if self.on_cancel:
            self.on_cancel()

    def refresh_conversation_list(self):
        if self.list_container is None:
            return
        self.list_container.remove_children()
        self._visible_buttons.clear()
        self._id_to_index.clear()
        filtered = self._filter_conversations()
        self._visible_conversations = filtered
        self._adjust_selection_after_refresh(len(filtered))
        if not filtered:
            self.list_container.mount(
                Static("No saved conversations yet.", classes="empty-state")
            )
            return
        for index, name in enumerate(filtered):
            btn_id = f"conversation-selector-option-{self._next_option_id}"
            self._next_option_id += 1
            button = Button(
                name,
                id=btn_id,
                variant="primary",
                classes="conversation-selector-option",
            )
            self.list_container.mount(button)
            self._visible_buttons.append(button)
            self._id_to_index[btn_id] = index
        self._apply_selection()

    def _filter_conversations(self) -> list[str]:
        query = self._search_value.strip().lower()
        if not query:
            return list(self.conversations)
        matches: list[tuple[float, int, str]] = []
        for index, name in enumerate(self.conversations):
            lower = name.lower()
            substring = query in lower
            ratio = SequenceMatcher(None, query, lower).ratio()
            if substring or ratio >= 0.35:
                score = ratio + (0.15 if substring else 0)
                matches.append((score, index, name))
        matches.sort(key=lambda item: (-item[0], item[1]))
        return [name for _, _, name in matches]

    def _schedule_refresh(self, value: str):
        self._search_value = value
        now = time.monotonic()
        elapsed = now - self._last_refresh
        if elapsed >= 0.2 and self._debounce_timer is None:
            self._run_refresh(now)
            return

        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        delay = max(0.2 - elapsed, 0)
        self._debounce_timer = self.set_timer(delay, self._handle_debounce)

    def _handle_debounce(self) -> None:
        now = time.monotonic()
        self._run_refresh(now)

    def _run_refresh(self, now: float) -> None:
        self._debounce_timer = None
        self._last_refresh = now
        if self.is_mounted:
            self.refresh_conversation_list()

    def _adjust_selection_after_refresh(self, length: int):
        if length == 0:
            self._selected_index = -1
            return
        if self._selected_index < 0:
            self._selected_index = 0
            return
        if self._selected_index >= length:
            self._selected_index = length - 1

    def move_selection(self, delta: int):
        if not self._visible_conversations:
            return
        if self._selected_index < 0:
            self._selected_index = 0
        self._selected_index = max(
            0,
            min(len(self._visible_conversations) - 1, self._selected_index + delta),
        )
        self._apply_selection()

    def select_current(self, index: int | None = None):
        if not self._visible_conversations:
            return
        if index is None:
            target = self._selected_index if self._selected_index >= 0 else 0
        else:
            target = index
        if target < 0 or target >= len(self._visible_conversations):
            return
        self._selected_index = target
        self._apply_selection()
        if self.on_select:
            self.on_select(self._visible_conversations[target])

    def _apply_selection(self):
        for idx, button in enumerate(self._visible_buttons):
            selected = idx == self._selected_index
            button.set_class(selected, "selected")
            if selected and hasattr(button, "scroll_visible"):
                button.scroll_visible(animate=False)


class OverlayContainer(Container):
    def __init__(
        self,
        popup: Widget,
    ):
        super().__init__()
        self.popup = popup

    def compose(self):
        yield self.popup
