# Skills Popup — Implementation Plan

> **Status: implemented.** `:skills` command + `SkillsPopup` widget, the
> `prune_active_skills` helper, and the builder-side active ⊆ available
> filter are in. Tests in `test/bond/tui/test_skills_popup.py`,
> `test/bond/test_skill.py`, and the builder test module. Docs in
> `docs/skills.md`. One deviation from the plan: the active toggle is bound to
> `shift+enter` (and the `●`/`○` row button) instead of a printable key,
> because a focused `Input` consumes all printable keys. Final keymap is
> vim-style with two focus modes (search / list): `tab` switches modes,
> `enter` applies, `esc` backs out of search then cancels, and in list mode
> `j`/`k` move, `a` toggles available, `s` toggles active, `q` cancels,
> `/` returns to search. Final semantics: `s` on an inactive skill activates
> it *and* makes it available in one step; deactivating keeps it available;
> `a` on an active skill makes it unavailable (and deactivates) directly.

Goal: a `:skills` TUI command that opens a popup to manage a conversation's
skills — which skills are *available* and which are *active* — without
touching the message history.

## Background / current state

- `Conversation.available_skills: list[str] | None` — `None` = inherit the
  persona's `available_skills`; an explicit list (possibly `[]`) overrides.
- `Conversation.active_skills: list[str]` — loaded skills; rendered as full
  SKILL.md blocks in `<active-skills>` of the system prompt, which is
  re-rendered on every `generate()` (so changes take effect next turn, no
  history scrubbing needed).
- `effective_available_skills(conversation, persona)` in `src/bond/skill.py`
  is the single resolver, shared by `load_skill`/`unload_skill` and the
  system message builder.
- `BondRuntime.list_skills()` / `get_skill(name)` enumerate/load skills from
  `~/.config/bond/skills/<name>/SKILL.md` (cached for process lifetime).
- Popups: `TuiPopup[T]` (`ModalScreen` + `PopupManager`), existing example
  `ConversationSelectorPopup` (search field with debounce + button rows +
  keyboard nav). Textual >= 8.2, so all modern widgets are available.
- Commands live in `TuiCommandHandler` (`:save`, `:load`, `:to`, ...), most
  gated on `self._app.is_idle` and run inside `agent_loop.pause()`.

## Open questions & decisions

### 1. What happens to `active_skills` when `available_skills` changes?

**Invariant: `active_skills ⊆ effective available_skills`.**

- The popup enforces this on Apply: unchecking "available" for a skill also
  removes it from the draft active set.
- Defense in depth (state can also diverge outside the popup, e.g. switching
  persona with `:to` while `available_skills is None`, or deleting a skill
  directory): the system message builder filters the `<active-skills>` block
  to the effective available list, so a stale active entry is skipped (with a
  warning) instead of injected into the prompt. `load_skill` already validates
  against the effective list.
- New pure helper in `src/bond/skill.py`:
  `prune_active_skills(conversation, available) -> list[str]` — removes
  active entries not in `available`, returns the removed names (for the
  notification). Unit-testable without Textual.
- We deliberately do NOT auto-prune on persona switch (`:to`): the old plan
  says the conversation's skill fields are left untouched on persona switch;
  the builder filter covers rendering. The popup Apply is the only place that
  prunes.

### 2. How are skills displayed and what is their "enabled" state?

Each row = one skill on disk (`runtime.list_skills()`, sorted), showing
`name` + `description` (from `get_skill`, tolerant of load errors → "<unreadable>").
Three visual states per row:

| state                 | marker       | css class                |
| --------------------- | ------------ | ------------------------ |
| available + active    | `[x] ● name` | `skill-row active`       |
| available, not active | `[x] ○ name` | `skill-row`              |
| not available         | `[ ]  name`  | `skill-row off` (dimmed) |

Skills referenced by the current available/active lists but missing on disk
are still shown, marked `(missing)`, so the user can remove them.

A mode line above the list shows how `available_skills` is currently resolved:
`Inheriting from persona '<name>': a, b` / `Custom: a, b` / `None (no skills)`.

### 3. Inherit vs. explicit list in the popup

Draft state: `_available: set[str] | None` where `None` = inherit mode.

- Toggling any row while in inherit mode materializes the draft from the
  current effective list, then applies the toggle (so you only override what
  you change).
- Buttons: **Reset** (back to inherit / `None`), **Clear** (explicit `[]`),
  **Select all** / **None** (of the filtered rows), **Cancel**, **Apply**.
- Apply with an untouched inherit mode returns `available_skills=None`
  (no materialization just by opening the popup).

Result type:

```python
class SkillsPopupResult:
    available_skills: list[str] | None  # None = inherit persona
    active_skills: list[str]             # already pruned to available
```

## UI design

New `src/bond/tui/widgets/skills_popup.py`, modeled on
`ConversationSelectorPopup`:

- Title + mode line (`Static`), search `Input` with 0.5 s debounce (same
  fuzzy filter as the conversation selector: substring or
  `SequenceMatcher` ratio >= 0.35, sorted by score),
- `ScrollableContainer` with one `Button` row per visible skill,
- button bar: Reset / Clear / Select all / Select none / Cancel / Apply.
- Keyboard: up/down, ctrl+k/ctrl+j, tab/shift+tab → move highlight;
  **enter or click → toggle available**; **space or `a` → toggle active**
  (no-op with a toast if the skill is not available); escape/ctrl+z → cancel.
- Footer hint line: `enter: available · space: active · esc: cancel`.
- Empty state: "No skills found in ~/.config/bond/skills" (or "No matching
  skills." when the filter matches nothing).
- CSS in `tui.css` mirroring the `ConversationSelectorPopup` block.

Draft logic kept in small pure-ish methods (`_toggle_available`,
`_toggle_active`, `_apply`) so it can be unit-tested via Textual's pilot
(`run_test()`) without a running agent loop.

## Wiring

- `BondTui.select_skills(...)` in `app.py`, mirroring `select_conversation`:
  pushes the popup via `popup_manager.show(...)` and awaits
  `popup.wait_for()`.
- `TuiCommandHandler`: new `:skills` command (alias `:skill`), parser entry in
  `_build_parser`.
  - Refuse when the agent is busy (`if not self._app.is_idle: return False`),
    same as `:save`/`:load`.
  - Inside `async with self._app.agent_loop.pause():`:
    1. Gather data: `runtime.list_skills()`, descriptions via
       `runtime.get_skill(name)` (try/except), persona name,
       `effective_available_skills(conversation, persona)`,
       `conversation.active_skills`.
    1. `result = await self._app.select_skills(...)`
    1. On `Success`: set `conversation.available_skills = result.available_skills`,
       prune active via `prune_active_skills` (plus whatever the popup already
       pruned), notify a summary
       (`Skills updated — available: inherit|a, b; active: x, y`
       - removed ones). Changes apply to the next `generate()` automatically.
    1. On `Failure` (cancelled): no changes.
  - The mutated fields are plain model fields, so they persist with the
    conversation metadata JSON on the next save/quit — no extra save logic.

## Builder safety filter

In `default_system_message_builder.py`, when rendering `<active-skills>`,
skip names not in the effective available list:

```python
available = effective_available_skills(conversation, persona_config)
...
for name in conversation.active_skills:
    if name not in available:
        logger.warning(f"Skipping active skill '{name}': not in available skills")
        continue
```

(`available` is already computed above for the `<available-skills>` block.)

## Files

| file                                                                | change                                                                                   |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `src/bond/tui/widgets/skills_popup.py`                              | new: `SkillsPopupResult`, `SkillsPopup`                                                  |
| `src/bond/tui/app.py`                                               | `select_skills(...)` helper                                                              |
| `src/bond/tui/command_handler.py`                                   | `:skills` command + parser entry                                                         |
| `src/bond/skill.py`                                                 | `prune_active_skills()` helper                                                           |
| `src/bond/providers/general/util/default_system_message_builder.py` | filter `<active-skills>` by effective available                                          |
| `src/bond/tui/tui.css`                                              | `SkillsPopup` styles (mirror conversation-selector)                                      |
| `test/bond/test_skill.py`                                           | tests for `prune_active_skills`                                                          |
| `test/bond/tui/test_skills_popup.py`                                | new: pilot tests for popup draft logic (toggle/reset/clear/apply/cancel, prune on apply) |
| `docs/skills.md`                                                    | document `:skills` popup + the active ⊆ available invariant                              |
| `README.md`                                                         | move "skills popup" from Future Features to implemented                                  |

## Optional (can be a follow-up)

- Status bar segment showing active skills (`Skills: a, b`), updated on popup
  apply and on persona/conversation switch.
- `unload` on persona switch instead of render-only filtering.

## Test plan

- `prune_active_skills`: removes stale entries, returns removed names, no-op
  when already consistent, empty available clears all.
- Builder: active skill not in available → not rendered, warning logged.
- Popup (Textual pilot, no agent loop needed): open → toggle available
  materializes from inherit; space toggles active only when available; Apply
  returns pruned result; Reset restores `None`; Clear gives `[]`; Escape →
  `Failure`.
- Command handler: `:skills` while busy returns False; while idle applies
  result to the conversation.
