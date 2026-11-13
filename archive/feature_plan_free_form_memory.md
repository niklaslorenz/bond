# Feature Plan: Free-Form Memory (FFM) + persona `active_skills`

## Overview

Free-Form Memory (FFM) is a structured, human-readable memory that complements the
existing vector-store memory (`store_memory` / `recall_memory` / `retire_memory`).
Instead of opaque embeddings, an FFM storage is a plain directory the agent reads
and writes with the ordinary file tools, plus an `index.md` at its root that
describes the directory structure and roughly what is stored where (README sketch,
"Future Features").

MVP design: an FFM storage is **just a managed directory conventionally named
`ffm`**, addressed via `bond://ffm/...`. The workflow rules (read `index.md`
first, keep it up to date, where to put things) are taught by a loadable **`ffm`
skill**. To make that skill reliably active, personas get a new **`active_skills`**
config option listing skills that start loaded in new conversations.

## Open questions / decisions

- **URI scheme**: reuse `bond://<name>/...` (zero new code); no dedicated
  `ffm://` scheme in the MVP. Decided: `bond://`.
- **Storage registry with ids**: not in the MVP. Multiple storages =
  multiple managed directories (`ffm-work`, `ffm-personal`, ...). Decided:
  naming convention only; a registry can come later if discovery becomes painful.
- **Read/write grants**: map to the existing `read_only` flag of managed
  directories (`read_only: true` = read grant, otherwise read-write). Decided.
- **index.md enforcement**: convention only, enforced by skill instructions.
  No core validation that index.md exists or is updated. Decided.
- **Auto-enable of the skill**: SKILL.md frontmatter only supports
  `name`/`description` (`src/bond/skill.py::_parse_skill_md`), so there is no
  real auto-load. Decided: solve it with persona `active_skills` (skill starts
  active in new conversations) + an advisory `description` telling the model to
  load the skill before touching `bond://ffm/...`.
- **Semantic indexing of FFM into a vector store**: explicitly out of scope
  (README: "maybe later").

## Design decisions

### 1. FFM storage = managed directory named `ffm` (convention)

Persona config:

```json
"managed_directories": [
  { "name": "ffm", "path": "~/bond/ffm" }
]
```

- All file tools (`read_file`, `create_file`, `apply_patch`, `search_file`,
  `grep`, `tree`, `list_directory`) already resolve `bond://ffm/index.md` etc.
  via `Persona.resolve_path()` / `ToolCallContext.resolve_path()` — no new tool
  code.
- `read_only: true` on the managed directory gives the "read but not write"
  grant; write tools refuse with a permission error (existing behavior).
- The `<managed-directories>` system-prompt section already lists the storage,
  so the model sees it without any prompt changes.
- **Convention to document**: the FFM managed directory should be named `ffm`.
  The skill instructions should refer to "the managed directory named `ffm` from
  the `<managed-directories>` section" instead of hardcoding the URI, so a
  rename degrades gracefully.

### 2. `ffm` skill carries the workflow

Lives at `~/.config/bond/skills/ffm/SKILL.md` (outside this repo; user config):

- frontmatter `description` advises: load this skill before reading/writing
  `bond://ffm/...`
- instructions: always read `bond://ffm/index.md` first; keep it updated when
  adding/moving/removing files; propose a sensible directory layout (e.g.
  `projects/`, `people/`, `preferences/`, `decisions/`); use `grep`/`tree` for
  discovery; prefer small focused markdown files.
- No skill-provided tools needed in the MVP — the builtin `file` toolset covers
  everything.

### 3. Persona `active_skills` (core change)

New field on `PersonaConfig` (`src/bond/persona.py`):

```python
active_skills: list[str] = Field(default_factory=list)
"""Skills that start active in new conversations with this persona."""
```

Semantics:

- Applied only when a conversation gets its persona for the **first time**
  (the `conversation.persona is None` write-back branch in
  `AsyncAgentLoop._reconcile_state`, `src/bond/behaviours/async_loop.py:271-274`)
  **and** `conversation.active_skills` is empty. Conversations loaded from disk
  (persona already set, persisted `active_skills`) are never touched — the
  user's saved state wins.
- Seeding writes into `conversation.active_skills`, so all existing machinery
  works unchanged: the `active ⊆ effective available` intersection in
  `_reconcile_skill_toolsets`, the `<active-skills>` system-prompt section, the
  `:skills` popup, and `load_skill`/`unload_skill`.
- A `model_validator` on `PersonaConfig` rejects entries not present in
  `available_skills` (fail fast on config typos; local skills from
  `use_local_skills` are resolved at runtime and merely filtered out with a
  warning, as today).

### Alternatives considered

- Dedicated `ffm://` URI scheme: clearer in prompts, but requires changes in
  `resolve_path` and duplicates the managed-directory machinery. Rejected for
  MVP.
- FFM registry (ids -> paths) in core config: more structure, but managed
  directories already provide naming + access control. Deferred.
- Builtin `ffm` toolset (e.g. `ffm_overview`): unnecessary — `read_file` +
  `tree` on `bond://ffm/` do the same. Deferred.
- Enforcement of index.md in core: would require intercepting writes; the skill
  convention is enough for an MVP. Deferred.

## Task list

### Core: persona `active_skills`

- [x] Add `active_skills` field to `PersonaConfig` in
  `src/bond/persona.py`, next to `available_skills`
- [x] Add `model_validator` on `PersonaConfig` enforcing
  `active_skills ⊆ available_skills` (clear error on violation)
- [x] Seed defaults in `AsyncAgentLoop._reconcile_state`
  (`src/bond/behaviours/async_loop.py`): when `conversation.persona` was
  `None` and `conversation.active_skills` is empty, set
  `conversation.active_skills = list(persona_config.active_skills)`
  (after the persona is loaded/instantiated in that branch)
- [x] Update the `_reconcile_state` docstring (it currently documents
  `active_skills` as strictly read-only)
- [x] Tests: persona config validation (subset enforced, extra="forbid" still
  works); seeding on fresh conversation; no re-seeding for loaded
  conversations with persisted `active_skills`; seeding when switching
  persona via `set_persona` does NOT clobber existing active skills
  (4 validator tests in `test/bond/test_skill.py`, 5 seeding tests in
  `test/bond/behaviours/test_async_loop.py`)
- [x] Docs: document `active_skills` in `docs/skills.md` next to
  `available_skills` / `use_local_skills` (this is the only FFM-adjacent
  repo doc — it documents the config option, not FFM itself)

### FFM convention + skill (user config only, NOT this repo)

FFM is a convention on top of managed directories + a skill, both of which live
in the user's config (`~/.config/bond/`). Per decision, nothing about FFM goes
into this repo's docs or README — the README "Free Form Memory" sketch stays as
the idea note. Remaining work, all outside the repo:

- [x] Move the drafted skill from `drafts/ffm-skill/SKILL.md` (this repo) to
  `~/.config/bond/skills/ffm/SKILL.md` once reviewed — workflow instructions
  (read `bond://ffm/index.md` first, keep it updated, suggested layout, use
  grep/tree) and an advisory `description` telling the model to load the
  skill before touching `bond://ffm/...`
- [x] Persona config in `~/.config/bond/personas/<name>.yaml`:
  `managed_directories: [{name: ffm, path: ~/bond/ffm}]` +
  `available_skills: ["ffm"]` + `active_skills: ["ffm"]`
- [x] Optionally keep the FFM conventions documented in the skill itself (or a
  README inside the ffm storage dir), not in this repo

### Verification

- [x] Full test suite passes
- [x] Manual end-to-end: persona with `active_skills: ["ffm"]` -> new
  conversation shows `<active-skills>` with ffm; agent can
  `read_file("bond://ffm/index.md")`; `read_only` storage refuses writes

## Notes

- Repo scope is limited to the `active_skills` persona option (+ its docs and
  tests). The FFM storage convention (`ffm` managed directory + `index.md`) and
  the `ffm` skill live entirely in the user's config dir (`~/.config/bond/`),
  so they are deliberately not documented in this repo.
