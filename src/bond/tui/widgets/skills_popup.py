"""Popup for managing a conversation's available and active skills.

Two independent states per skill:

- *available* — the skill may be activated (``conversation.available_skills``;
  ``None`` means "inherit the persona's list").
- *active* — the skill is currently loaded (``conversation.active_skills``);
  its SKILL.md is rendered into the system prompt.

Invariant: active skills are always a subset of the available ones. Unchecking
"available" also removes the skill from the active draft; activating a skill
implies making it available (deactivating keeps it available). Apply prunes
again (defense in depth — the system message builder filters as well).

Draft semantics: ``_available is None`` means inherit mode. The first toggle
materializes the effective list into an explicit set; the Reset button goes
back to ``None``.

Keymap (vim-style, two focus modes):

- anywhere: ``up``/``down``/``ctrl+k``/``ctrl+j`` move, ``enter`` applies,
  ``tab`` switches mode, ``ctrl+z`` cancels.
- list focused (default): ``j``/``k`` move, ``space`` toggles available,
  ``shift+space`` toggles active (implies available), ``q`` cancels,
  ``/`` switches to search, ``esc`` cancels.
- search focused: type to filter, ``esc``/``tab`` switch to list.
"""

from difflib import SequenceMatcher

from pydantic import BaseModel
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.events import DescendantFocus, Key
from textual.timer import Timer
from textual.widgets import Button, Input, Static

from bond.tui.widgets.popup import TuiPopup


class SkillInfo(BaseModel):
    """Display info for one skill row."""

    name: str
    description: str = ""
    missing: bool = False  # referenced by the conversation but not on disk


class SkillsPopupResult(BaseModel):
    """What the popup returns on Apply.

    ``available_skills=None`` keeps the conversation in inherit mode.
    ``active_skills`` is already pruned to the available set.
    """

    available_skills: list[str] | None
    active_skills: list[str]


class SkillsPopup(TuiPopup[SkillsPopupResult], Vertical):
    def __init__(
        self,
        skills: list[SkillInfo],
        persona_name: str,
        persona_available_skills: list[str],
        conversation_available_skills: list[str] | None,
        active_skills: list[str],
    ):
        super().__init__()
        self._persona_name = persona_name
        self._persona_available = list(persona_available_skills)
        self._effective_available = (
            list(conversation_available_skills)
            if conversation_available_skills is not None
            else self._persona_available
        )
        # Draft state: None = inherit mode, set = explicit custom list
        self._available: set[str] | None = (
            set(conversation_available_skills)
            if conversation_available_skills is not None
            else None
        )
        # Defensive prune on open: active must be a subset of available
        self._active: set[str] = set(active_skills) & set(self._effective_available)

        # Union of on-disk skills and skills referenced by the conversation
        by_name = {info.name: info for info in skills}
        referenced = set(self._effective_available) | set(active_skills)
        for name in sorted(referenced - set(by_name)):
            by_name[name] = SkillInfo(name=name, missing=True)
        self._all_skills: list[SkillInfo] = [by_name[name] for name in sorted(by_name)]

        self._search_value: str = ""
        self._search_timer: Timer | None = None
        self._list_focused = True  # False = search field focused (list mode off)
        self._visible_skills: list[SkillInfo] = []
        self._selected_index: int = -1
        self._next_option_id = 1
        self._option_id_to_index: dict[str, int] = {}
        self._active_id_to_index: dict[str, int] = {}
        self._row_buttons: list[Button] = []

        self._title = Static("Manage Skills", classes="skills-popup-title")
        self._mode_label = Static("", classes="skills-popup-mode")
        self._search_field = Input(
            placeholder="Search skills", id="skills-popup-search"
        )
        self._list_container = ScrollableContainer(classes="skills-popup-list")
        self._hint = Static("", classes="skills-popup-hint")
        self._reset_button = Button(
            "Reset (persona)", id="skills-popup-reset", variant="default"
        )
        self._clear_button = Button("Clear", id="skills-popup-clear")
        self._all_button = Button("All", id="skills-popup-all")
        self._none_button = Button("None", id="skills-popup-none")
        self._cancel_button = Button(
            "Cancel", id="skills-popup-cancel", variant="error"
        )
        self._apply_button = Button("Apply", id="skills-popup-apply", variant="primary")

    def compose(self):
        yield self._title
        yield self._mode_label
        yield self._search_field
        yield self._list_container
        yield self._hint
        with Horizontal(classes="button-bar"):
            yield self._reset_button
            yield self._clear_button
            yield self._all_button
            yield self._none_button
            yield self._cancel_button
            yield self._apply_button

    async def on_mount(self):
        await self._refresh()
        self._update_hint()
        if self._list_focused:
            self._focus_list()
        else:
            self._focus_search()

    # Focus mode helpers

    def _update_hint(self):
        if self._list_focused:
            self._hint.update(
                "j/k: move · space: available · shift+space: active · "
                "q: cancel · / : search · tab: search · enter: apply"
            )
        else:
            self._hint.update("type: filter · tab/esc: list · enter: apply")

    def _focus_list(self):
        self._list_focused = True
        self._list_container.focus()
        self._update_hint()

    def _focus_search(self):
        self._list_focused = False
        self._search_field.focus()
        self._update_hint()

    def on_descendant_focus(self, event: DescendantFocus):
        # Mouse clicks can move focus directly; keep the mode flag in sync.
        # "List mode" simply means the search field is not focused.
        self._list_focused = event.widget is not self._search_field
        self._update_hint()

    # State helpers

    def _current_available(self) -> set[str]:
        if self._available is not None:
            return self._available
        return set(self._effective_available)

    def _is_available(self, name: str) -> bool:
        return name in self._current_available()

    def _row_label(self, info: SkillInfo) -> str:
        box = "✔" if self._is_available(info.name) else "✗"
        dot = "●" if info.name in self._active else "○"
        desc = f" — {info.description}" if info.description else ""
        missing = " (missing)" if info.missing else ""
        return f"{dot} {box} {info.name}{desc}{missing}"

    def _mode_text(self) -> str:
        if self._available is None:
            names = ", ".join(self._effective_available) or "none"
            return (
                f"Available skills: inheriting from persona "
                f"'{self._persona_name}' ({names})"
            )
        names = ", ".join(sorted(self._available)) or "none"
        return f"Available skills: custom ({names})"

    # Draft mutations

    async def _toggle_available(self, name: str):
        if self._available is None:
            # Materialize the inherited list on first change
            self._available = set(self._effective_available)
        if name in self._available:
            self._available.discard(name)
            self._active.discard(name)  # invariant: active ⊆ available
        else:
            self._available.add(name)
        await self._refresh()

    async def _toggle_active(self, name: str):
        if name in self._active:
            # Deactivate only — the skill stays available.
            self._active.discard(name)
        else:
            # Activating implies availability.
            if self._available is None:
                self._available = set(self._effective_available)
            self._available.add(name)
            self._active.add(name)
        await self._refresh()

    async def _select_all_visible(self):
        if self._available is None:
            self._available = set(self._effective_available)
        # Filter by the current search value, not the last rendered rows:
        # `_visible_skills` may be stale if the search changed but no
        # refresh ran yet.
        for info in self._filter_skills():
            self._available.add(info.name)
        await self._refresh()

    async def _select_none_visible(self):
        if self._available is None:
            self._available = set(self._effective_available)
        for info in self._filter_skills():
            self._available.discard(info.name)
            self._active.discard(info.name)
        await self._refresh()

    async def _clear_all(self):
        self._available = set()
        self._active = set()
        await self._refresh()

    async def _reset_to_persona(self):
        self._available = None
        # active stays, but is re-pruned against the effective list on apply;
        # prune now too so the UI shows the consistent state immediately
        self._active &= set(self._effective_available)
        await self._refresh()

    def _apply(self):
        base = self._current_available()
        available = None if self._available is None else sorted(self._available)
        active = sorted(self._active & base)
        self.finish(SkillsPopupResult(available_skills=available, active_skills=active))

    # Rendering

    async def _refresh(self):
        self._mode_label.update(self._mode_text())
        self._list_container.remove_children()
        self._row_buttons.clear()
        self._option_id_to_index.clear()
        self._active_id_to_index.clear()
        self._next_option_id = 1
        filtered = self._filter_skills()
        self._visible_skills = filtered
        self._adjust_selection_after_refresh()
        if not filtered:
            empty_text = (
                "No matching skills."
                if self._search_value.strip()
                else "No skills found."
            )
            self._list_container.mount(Static(empty_text, classes="empty-state"))
            return
        for index, info in enumerate(filtered):
            option_id = f"skills-popup-option-{self._next_option_id}"
            active_id = f"skills-popup-active-{self._next_option_id}"
            self._next_option_id += 1
            option_button = Button(
                self._row_label(info),
                id=option_id,
                classes="skill-option",
            )
            option_button.can_focus = False
            if not self._is_available(info.name):
                option_button.add_class("off")
            if info.name in self._active:
                option_button.add_class("active-row")
            row = Horizontal(option_button, classes="skill-row")
            self._list_container.mount(row)
            self._row_buttons.append(option_button)
            self._option_id_to_index[option_id] = index
            self._active_id_to_index[active_id] = index
        self._apply_selection_class()

    def _filter_skills(self) -> list[SkillInfo]:
        query = self._search_value.strip().lower()
        if not query:
            return list(self._all_skills)
        matches: list[tuple[float, int, SkillInfo]] = []
        for index, info in enumerate(self._all_skills):
            haystack = f"{info.name} {info.description}".lower()
            substring = query in haystack
            ratio = SequenceMatcher(None, query, haystack).ratio()
            if substring or ratio >= 0.35:
                score = ratio + (0.15 if substring else 0)
                matches.append((score, index, info))
        matches.sort(key=lambda item: (-item[0], item[1]))
        return [info for _, _, info in matches]

    def _adjust_selection_after_refresh(self):
        length = len(self._visible_skills)
        if length == 0:
            self._selected_index = -1
            return
        if self._selected_index < 0:
            self._selected_index = 0
            return
        if self._selected_index >= length:
            self._selected_index = length - 1

    def _move_selection(self, delta: int):
        if not self._visible_skills:
            return
        if self._selected_index < 0:
            self._selected_index = 0
        self._selected_index = max(
            0, min(len(self._visible_skills) - 1, self._selected_index + delta)
        )
        self._apply_selection_class()

    def _selected_skill(self) -> SkillInfo | None:
        if 0 <= self._selected_index < len(self._visible_skills):
            return self._visible_skills[self._selected_index]
        return None

    def _apply_selection_class(self):
        for idx, button in enumerate(self._row_buttons):
            selected = idx == self._selected_index
            button.set_class(selected, "selected")
            if selected:
                button.scroll_visible(animate=False)

    # Event handling

    def on_input_changed(self, event: Input.Changed):
        if event.input.id != "skills-popup-search":
            return
        self._search_value = event.value
        if self._search_timer is None:
            self._search_timer = self.set_timer(0.5, self._on_search_timer)

    async def _on_search_timer(self):
        self._search_timer = None
        await self._refresh()

    async def on_key(self, event: Key):
        key = event.key
        # Works in both modes (non-printable, bubbles from the search field).
        if key in ("up", "ctrl+k"):
            event.stop()
            self._move_selection(-1)
            return
        if key in ("down", "ctrl+j"):
            event.stop()
            self._move_selection(1)
            return
        if key == "tab":
            event.stop()
            if self._list_focused:
                self._focus_search()
            else:
                self._focus_list()
            return
        if key == "enter":
            event.stop()
            self._apply()
            return
        if key == "ctrl+z":
            event.stop()
            self.finish(None)
            return
        if key == "escape":
            event.stop()
            if not self._list_focused:
                # From the search field: back out to the list.
                self._focus_list()
            else:
                self.finish(None)
            return
        # List mode only: printable keys never reach us while the search
        # field is focused (the Input stops them).
        if not self._list_focused:
            return
        if key == "j":
            event.stop()
            self._move_selection(1)
            return
        if key == "k":
            event.stop()
            self._move_selection(-1)
            return
        if key == "space":
            event.stop()
            skill = self._selected_skill()
            if skill is not None:
                await self._toggle_available(skill.name)
            return
        if key == "shift+space":
            event.stop()
            skill = self._selected_skill()
            if skill is not None:
                await self._toggle_active(skill.name)
            return
        if key == "q":
            event.stop()
            self.finish(None)
            return
        if key == "slash":  # pilot/terminals report "/" as the "slash" key
            event.stop()
            self._focus_search()
            return

    async def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id is None:
            return
        if button_id == "skills-popup-cancel":
            self.finish(None)
            return
        if button_id == "skills-popup-apply":
            self._apply()
            return
        if button_id == "skills-popup-reset":
            await self._reset_to_persona()
            return
        if button_id == "skills-popup-clear":
            await self._clear_all()
            return
        if button_id == "skills-popup-all":
            await self._select_all_visible()
            return
        if button_id == "skills-popup-none":
            await self._select_none_visible()
            return
