# Feature plan: `use_local_skills` persona config field

## Overview

Today, local skills from `.bond/skills/` are only usable when they are listed
in the persona's `available_skills` (or toggled on per-conversation via the
skills popup). This feature adds a persona config field:

```json
{ "name": "...", "use_local_skills": true, ... }
```

Flow:

- `use_local_skills=True` and the conversation has **no own** `available_skills`
  list (inherit mode): all local skills from the closest `.bond/skills/` are
  considered available, **in addition to** the persona's `available_skills`.
- The conversation has its own `available_skills` list: that list wins
  unchanged (precedence preserved).
- `use_local_skills=False` (default): exactly today's behavior.
- `--disable-local-config` / no `.bond` dir: no local skills, regardless of
  the flag.

## Open questions / decisions

- **Field name/type**: `use_local_skills: bool = False` on `PersonaConfig`
  (pydantic, default False → fully backwards compatible; `extra="forbid"`
  loading means old configs without the field still validate).
- **Union or replace**: when `use_local_skills=True`, the effective list is
  persona `available_skills` **plus** all local skill names (deduped, persona
  list first, then sorted local names). Decision: additive — the persona list
  still works as before, locals just become available too.
- **Where the logic lives**: `effective_available_skills()` in
  `src/bond/skill.py` — the single source of truth already shared by
  `skill_tools.py` (load/unload), `default_system_message_builder.py` (system
  prompt listing), `async_loop.py` (pruning active skills), and the TUI
  command handler. Conversation-list precedence is already the first branch
  there; we only extend the persona fallback.
- **Enumerating local skills**: new `BondRuntime.list_local_skills()` method
  returning the names of `.bond/skills/*/` dirs containing a `SKILL.md`
  (empty when local config is disabled or there is no `.bond`). Mirrors the
  local-skill loop already inside `list_skills()`; `get_skill()` shadowing is
  unchanged. `effective_available_skills` lazy-imports `BondRuntime` (same
  pattern as `persona.py`) to avoid a circular import.
- **TUI popup**: the popup currently receives `persona.config.available_skills`
  as "persona available". The command handler will pass
  `effective_available_skills(Conversation(), persona)` instead, so local
  skills show as available in the popup when the flag is on (and "Reset
  (persona)" still means inherit mode → `None`).

## Design decisions

- Additive, opt-in, default-off: zero behavior change for existing configs.
- Conversation-level explicit list always wins (matches the user's spec and
  the existing invariant `active ⊆ available` via `prune_active_skills`).
- No changes to `get_skill()`/shadowing or to `list_skills()`.

## Task list

- [x] `src/bond/persona.py`: `use_local_skills: bool = False` field on `PersonaConfig` (default off → old configs unchanged).
- [x] `src/bond/runtime.py`: `list_local_skills()` — local skill dirs with `SKILL.md` under `get_local_skills_path()`, `[]` when disabled / no `.bond`.
- [x] `src/bond/skill.py`: `effective_available_skills()` extends the persona fallback with local skill names when `use_local_skills=True` (lazy `BondRuntime` import to avoid a cycle; dedup; conversation list still wins; `None` persona → `[]`). All consumers (skill tools, system message builder, agent loop, popup) inherit this automatically.
- [x] `src/bond/tui/command_handler.py`: popup now receives `effective_available_skills(Conversation(), persona)` as the persona-level list, so local skills show as available when the flag is on.
- [x] Tests: `test/bond/test_skill.py` — new `TestEffectiveAvailableSkillsUseLocalSkills` (flag off unchanged, flag on adds locals in inherit mode, dedupe, conversation list wins, instantiated Persona works, None persona empty, default False). `test/bond/test_local.py` — new `TestListLocalSkills` (lists local dirs with SKILL.md, skips dirs without, ignores global skills, empty without `.bond`, empty when disabled).
- [x] Full test suite green: **879 passed** (run via `.bond/scripts/run-tests.sh` through `run_local_script`), no regressions.
- [x] Docs: `docs/skills.md` (new `use_local_skills` section + tri-state table note) and `docs/local-bond-dir.md` (pointer).

## Progress / changes

- `src/bond/persona.py`, `src/bond/runtime.py`, `src/bond/skill.py`, `src/bond/tui/command_handler.py` as above.
- Tests: 6 new in `test_skill.py`, 3 new in `test_local.py`.
- Docs: `docs/skills.md`, `docs/local-bond-dir.md`.
- No deviations from the plan.
- Refinement after review: `effective_available_skills(conversation=None, persona=None)` — the conversation parameter is now optional; `None` means "inherit mode" without constructing a dummy `Conversation` (avoids its episode-buffer setup cost). `TuiCommandHandler` now passes `None` for the persona-level list. Also fixes a latent crash in `skill_tools.py`, which could pass `context.conversation=None`. 3 more tests added; suite green: **882 passed**.
