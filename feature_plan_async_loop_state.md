# Feature plan: rework `AsyncAgentLoop` state ownership (README TODO)

## Goal

Replace the `_build_turn()` rebuild pattern in `AsyncAgentLoop`
(`src/bond/behaviours/async_loop.py`) with a single **reconcile** pass that
derives all loop-held state from `self._conversation` before every turn —
the same pattern `_check_skill_toolsets()` already uses for skill toolsets.
The loop should stop mutating the conversation (pruning `active_skills`,
writing the default persona) as a side effect of building state.

## Current state (inspected)

- `__init__` calls `_build_turn()` → sets `_agent_turn`, `_persona`,
  `_persona_toolbox`, and as **side effects**: mutates
  `_tool_call_context.persona/.conversation`, prunes
  `conversation.active_skills` via `prune_active_skills`, writes
  `conversation.persona = <default>` when unset, unsubscribes/resubscribes
  the turn status observable, releases the old persona/toolbox.
- `set_persona()` / `set_conversation()` mutate the conversation under
  `pause()`, then call `_build_turn()` + `_signal_buffer._clear()`.
- `_run()` calls `_check_skill_toolsets()` before each turn, which diffs
  `conversation.active_skills` against `self._loaded_skill_toolsets` and
  adds/removes toolsets in `_skill_toolbox`.
- Consumers of conversation skill state: `skill_tools.py` (load/unload
  mutate `conversation.active_skills`), the system message builder (already
  guards `name not in available`), `tui/command_handler.py` (prunes at the
  popup edge), `tui/widgets/skills_popup.py`.
- `AsyncAgentLoop` currently has **no tests** (`test/bond/behaviours/` does
  not exist). Construction sites: `tui/main.py`, `cli/_interactive.py`,
  `cli/ask.py` — constructor signature must stay unchanged.

## Design decisions

1. **One reconcile method, three call sites.** Replace `_build_turn()` with
   `_reconcile_state()` (no return value; mutates held attrs only when the
   derived inputs changed):
   - called in `__init__`,
   - called at the top of every `_run()` iteration right where
     `_check_skill_toolsets()` is today (i.e. after a generation signal
     arrives, before `turn.run`), folding skill-toolset reconciliation into
     it,
   - called by `set_persona()` / `set_conversation()` after mutating the
     conversation (still under `pause()`), followed by
     `_signal_buffer._clear()`.
2. **Persona derivation.** `persona_id = conversation.persona or
   self._default_persona_id`. If the id changed since last reconcile (or it's
   the first call): fetch config via `runtime.get_persona`, `instantiate()`,
   `build_toolbox()`, build a new `AsyncAgentTurn` (subscribe
   `_on_turn_status_update`), release old persona + old persona toolbox.
   If unchanged: keep everything (no rebuild, no release).
3. **`ToolCallContext` sync in one place.** `tool_call_context.persona` /
   `.conversation` are assigned in `_reconcile_state()` every time (cheap,
   idempotent) — removes the "dirty hack" TODO comment by making it an
   explicit, single-purpose step instead of a hidden side effect.
4. **Derive, don't prune, skill state.** `_check_skill_toolsets` becomes
   part of reconcile and computes
   `effective_active = [s for s in conversation.active_skills if s in effective_available_skills(conversation, persona)]`,
   then diffs that against `_loaded_skill_toolsets`. The loop **never
   writes `conversation.active_skills`** anymore; stale entries are ignored
   (logged) rather than removed. `prune_active_skills` stays for the
   user-driven TUI popup edge (`command_handler.py`), which is where
   persistence of the prune actually belongs.
5. **No conversation-identity tracking** (user simplification after first
   implementation): only the *contents* of the conversation matter.
   `_reconcile_state()` keys the persona rebuild solely on the derived
   persona id; skill toolsets are reconciled purely by content diff in
   `_reconcile_skill_toolsets()`, which already handles conversation switches
   correctly (old conversation's skills drop out of the diff, new ones load).
6. **Default persona write-back: kept, but explicit.** `conversation.persona
   = persona_id` when unset still happens (so a saved conversation remembers
   its persona), but as a single clearly-commented line in reconcile — the
   only conversation field the loop writes, and only this one.
7. **"Cannot rebuild while busy" guard** moves out of the build method into
   `set_persona`/`set_conversation` (both already hold `pause()`, so the
   condition reduces to an assertion). Reconcile from `_run()` happens
   strictly between turns, which is safe.
8. **Public API unchanged.** Constructor signature, `persona` property,
   `prompt`, `start/stop/cancel/pause/interrupt/release`, `summarize`,
   `set_persona`, `set_conversation` all keep their signatures, so
   `tui/main.py`, `cli/_interactive.py`, `cli/ask.py`, `tui/app.py`,
   `tui/command_handler.py` need no changes.

## Open questions for the user — RESOLVED

- (Q1) Keep the single write-back `conversation.persona = <default>` —
  **confirmed by user**: a saved conversation should resume with the correct
  persona. Implemented in `_reconcile_state()`.
- (Q2) Loop derives the effective active-skill subset instead of pruning
  `conversation.active_skills` — **confirmed by user**. Stale entries persist
  in the saved metadata but are ignored (logged) by the loop; pruning stays
  at the user-driven edge (`command_handler.py` skills popup).

## Tasks

- [x] `async_loop.py`: `_reconcile_state()` implementing decisions 2–5, called
      from `__init__`, top of every `_run()` iteration, and
      `set_persona()`/`set_conversation()`; `_build_turn()` and the old
      `_check_skill_toolsets()` deleted; busy-guard moved to an explicit
      `_in_turn` flag set around `turn.run()`/`_handle_tool_calls()`
      (decision 7) so reconcile-from-`_run()` between turns is allowed
- [x] `async_loop.py`: `_reconcile_skill_toolsets()` computes
      `active ∩ effective_available`, never writes `active_skills`; add/remove/
      release semantics unchanged; conversation switches need no special
      handling — the content diff in `_reconcile_skill_toolsets()` swaps
      toolsets (user removed the identity check)
- [x] verified no other callers of `_build_turn`/`_check_skill_toolsets`;
      public API unchanged, so no TUI/CLI changes needed
- [x] `test/bond/behaviours/test_async_loop.py` (new; the loop previously had
      no tests): init derivation + persona write-back, conversation persona
      wins, invalid persona raises + error event, idempotent reconcile,
      stale active skill ignored-not-pruned (with warning), persona-level
      available skills, load/unload on `active_skills` change, unknown skill
      doesn't crash, `set_persona` rebuild/release/context-sync + no-op on
      same id, `set_conversation` swaps skill toolsets by content + write-back,
      `_in_turn` guard, `release()`, combined available tools
- [ ] run full test suite + formatter (user side)
- [x] README.md: "Rethink `AsyncAgentLoop` state ownership" TODO removed
