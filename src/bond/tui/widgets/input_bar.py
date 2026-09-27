from typing import Any, Callable

from textual.events import Key
from textual.message import Message
from textual.widgets import TextArea

from bond.tui.widgets.chat_log import ChatLog, ChatMessage


# DEPRECATED
class MultiLineInput(TextArea):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _get_tui_app(self):
        app = getattr(self, "app", None)
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

    async def on_key(self, event: Key) -> None:
        key = event.key
        if self._handle_scroll_shortcut(key, event):
            return
        if key == "shift+enter":
            self.insert("\n", self.cursor_location)
            self.move_cursor_relative(rows=1)
        elif key == "enter":
            event.prevent_default()
            msg = self.Submitted(self.text)
            self.post_message(msg)
            if msg.is_accepted():
                self.clear()

    class Submitted(Message):
        """Event emitted when Enter is pressed without Ctrl."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value
            self._accepted = False

        def accept(self):
            self._accepted = True

        def is_accepted(self) -> bool:
            return self._accepted


class InputBar(TextArea):

    class Submitted(Message):
        """Event emitted when Enter is pressed without Ctrl."""

        def __init__(self, value: str, callback: Callable[[], Any] | None) -> None:
            super().__init__()
            self.value = value
            self._callback = callback
            self._accepted = False

        def accept(self):
            self._accepted = True
            if self._callback is not None:
                self._callback()

        def is_accepted(self) -> bool:
            return self._accepted

    def on_key(self, event: Key) -> None:
        key = event.key
        if key == "shift+enter":
            self.insert("\n", self.cursor_location)
            event.prevent_default()
            event.stop()
        elif key == "enter":
            msg = self.Submitted(self.text, self.clear)
            self.post_message(msg)
            event.prevent_default()
            event.stop()
