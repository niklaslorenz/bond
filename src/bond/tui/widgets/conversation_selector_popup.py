import asyncio
from difflib import SequenceMatcher

from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.events import Key
from textual.widgets import Button, Input, Static

from bond.tui.debouncer import Debouncer
from bond.tui.widgets.popup import TuiPopup


class ConversationSelectorPopup(TuiPopup[str], Vertical):
    def __init__(
        self,
        conversations: list[str],
    ):
        super().__init__()
        self.conversations = conversations
        self._update_debouncer = Debouncer(self.refresh_conversation_list, 0.5)

        self._cancel_button = Button(
            "Cancel",
            variant="error",
            id="conversation-selector-cancel-button",
        )
        self._list_container: ScrollableContainer = ScrollableContainer(
            classes="conversation-selector-list"
        )
        self._search_field = Input(
            placeholder="Search conversations",
            id="conversation-selector-search",
        )

        self._id_to_index: dict[str, int] = {}
        self._search_value: str = ""
        self._visible_buttons: list[Button] = []
        self._visible_conversations: list[str] = []
        self._selected_index: int = -1
        self._next_option_id = 1

    def compose(self):
        yield Static("Load Conversation", classes="conversation-selector-title")
        yield self._search_field
        yield self._list_container
        with Horizontal(classes="button-bar"):
            yield self._cancel_button

    async def on_mount(self):
        await self.refresh_conversation_list()
        self._search_field.focus()

    # Control

    async def refresh_conversation_list(self):
        self._list_container.remove_children()
        self._visible_buttons.clear()
        self._id_to_index.clear()
        self._next_option_id = 1
        self._selected_index = 0
        filtered = self._filter_conversations()
        self._visible_conversations = filtered
        self._adjust_selection_after_refresh()
        if len(filtered) == 0:
            self._list_container.mount(
                Static("No matching conversations.", classes="empty-state")
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
            self._list_container.mount(button)
            self._visible_buttons.append(button)
            self._id_to_index[btn_id] = index
        self._apply_selection_class()

    # Event Handling

    async def on_input_changed(self, event: Input.Changed):
        if event.input.id != "conversation-selector-search":
            return
        self._search_value = event.value
        await self._update_debouncer()

    def on_key(self, event: Key):
        key = event.key
        if key in ("up", "ctrl+k", "shift+tab"):
            event.stop()
            self._move_selection(-1)
            return
        if key in ("down", "ctrl+j", "tab"):
            event.stop()
            self._move_selection(1)
            return
        if key == "enter":
            event.stop()
            self._select_current()
            return
        if key == "escape" or event.key == "ctrl+z":
            self.finish(None)
            event.stop()
            return

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "conversation-selector-cancel-button":
            self.finish(None)
            return

        if event.button.id is None:
            return
        idx = self._id_to_index.get(event.button.id)
        if idx is not None:
            self.finish(self._visible_conversations[idx])

    # Helper

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

    def _adjust_selection_after_refresh(self):
        length = len(self._visible_conversations)
        if length == 0:
            self._selected_index = -1
            return
        if self._selected_index < 0:
            self._selected_index = 0
            return
        if self._selected_index >= length:
            self._selected_index = length - 1

    def _move_selection(self, delta: int):
        if len(self._visible_conversations) == 0:
            return
        if self._selected_index < 0:
            self._selected_index = 0
        self._selected_index = max(
            0,
            min(len(self._visible_conversations) - 1, self._selected_index + delta),
        )
        self._apply_selection_class()

    def _select_current(self):
        if len(self._visible_conversations) == 0:
            return
        target = self._selected_index if self._selected_index >= 0 else 0
        if target < 0 or target >= len(self._visible_conversations):
            return
        self._selected_index = target
        self.finish(self._visible_conversations[target])

    def _apply_selection_class(self):
        for idx, button in enumerate(self._visible_buttons):
            selected = idx == self._selected_index
            button.set_class(selected, "selected")
            if selected:
                button.scroll_visible(animate=False)
