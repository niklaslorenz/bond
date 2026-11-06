# Skill Refactoring — Task List

Goal: turn the current `{SKILL:name}` prompt macros into real, directory-based
skills that can be activated per conversation, with structured metadata
(name / description / instructions) resolved by the runtime and rendered into
the system prompt by the system message builder.

The old macro mechanism moves to a new "prompts" feature.

## Design decisions (locked in)

- **Prompts (old skills)**: `~/.config/bond/prompts/*.md`, macro `{PROMPT:name}`,
  runtime methods `list_prompts` / `get_prompt` / `load_prompt`,
  `resolve_prompts()` in `util.py`.
- **Skills (new)**: `~/.config/bond/skills/<name>/SKILL.md` with `--- name / description ---` frontmatter (parsed manually, no yaml dependency).
  Body = instructions. Frontmatter `name` falls back to the directory name.
- **Skill object**: pydantic model `Skill(name, description, instructions)` in
  `src/bond/skill.py` + `parse_skill_md(text, fallback_name)`.
- **Runtime**: env ABC gets `list_skills()` / `load_skill(name) -> Skill`;
  `StaticRuntimeEnvironment` takes `skills: dict[str, Skill]` (tests);
  `DynamicRuntimeEnvironment` globs skill dirs; runtime caches skills in
  `_loaded_skills` (`NamedEntryRegistry[Skill]`). Cache is process-lifetime —
  editing a SKILL.md needs a restart.
- **Conversation**: `available_skills: list[str] | None = None`
  (`None` = inherit persona's list), `active_skills: list[str] = []` (plain list,
  stores skill *names* only; content resolved at render time).
- **Persona**: `PersonaConfig.available_skills: list[str] = []`.
- **Effective available skills** resolved in ONE helper so tool and builder
  agree: `conversation.available_skills if not None else persona.config.available_skills`.
- **Tools**: `load_skill` / `unload_skill` in `src/bond/tools/skill_tools.py`,
  registered as a builtin `PythonToolset("skills", ...)` in `_default_toolsets`
  (toolbox stays static — dynamic skill-toolsets are a later phase).
  `load_skill` verifies the name against effective available skills, appends to
  `conversation.active_skills`, and returns only a short confirmation — the
  skill content is NOT put into the tool result, because it is rendered into
  the system prompt by the builder (single source; avoids duplicating it into
  the message history). `unload_skill` removes from `active_skills`.
  Deactivation needs no prompt scrubbing: the system message is re-rendered
  fresh every `generate()`, never stored in history.
- **System prompt**: sections rendered by `DefaultSystemMessageBuilder` (NOT
  the message list builder): `<available-skills>` (`- name: description` lines)
  and `<active-skills>` (full per-skill blocks). Builder gets an optional
  `runtime` constructor param (falls back to `BondRuntime.get_instance()`) to
  resolve the persona via `conversation.persona`, plus an `include_skills`
  flag: `True` for generation builders (mistral/ollama), `False` for
  summarization / thought-condensation builders.
- **Toolbox sync on persona switch**: DEFERRED on purpose — `_build_turn()`
  rebuilds the toolbox from the persona, which drops skill toolsets. Ignored
  for now because skills have no tools yet.

## Tasks

### Phase 1 — Rename current skills to "prompts"

- [x] Rename `~/.config/bond/skills/` → `prompts/` in `DynamicRuntimeEnvironment`
- [x] Rename env ABC + both implementations + runtime methods:
  `list_skills`/`load_skill`/`get_skill` → `list_prompts`/`load_prompt`/`get_prompt`
- [x] Rename runtime cache `_loaded_skills` → `_loaded_prompts`
- [x] Rename `resolve_skills` → `resolve_prompts` in `util.py`, macro `{SKILL:x}` → `{PROMPT:x}`
- [x] Update call sites: `generation.py`, `summarization.py`,
  `thought_condensation.py`, `tool_loop_runner.py`
- [x] Update `test/bond/providers/general/util/test_tool_loop_runner.py`
  (mocks + `{PROMPT:...}` strings)
- [x] Decide migration story for existing users' `skills/` dir
  (auto-migrate on startup vs. docs note)

### Phase 2 — Skill model + runtime API

- [x] Create `src/bond/skill.py`: `Skill` pydantic model + `parse_skill_md()`
- [x] Add `list_skills()` / `load_skill(name) -> Skill` to `RuntimeEnvironment` ABC
- [x] `StaticRuntimeEnvironment`: accept `skills: dict[str, Skill]`
- [x] `DynamicRuntimeEnvironment`: `list_skills()` globs `skills/*/SKILL.md` dirs;
      `load_skill` reads + parses `skills/<name>/SKILL.md`
- [x] `BondRuntime`: `list_skills()`, `get_skill()` with `_loaded_skills` cache
- [x] Tests for the SKILL.md frontmatter parser (incl. fallback name)
      → `test/bond/test_skill.py` (parser + both envs + runtime cache)

### Phase 3 — Data model: conversation + persona fields

- [x] `Conversation`: add `available_skills: list[str] | None = None`,
      `active_skills: list[str] = []`
- [x] `PersonaConfig`: add `available_skills: list[str] = []`
- [x] Add `effective_available_skills(conversation, persona)` helper (single
      source of truth for tool + builder) — in `bond/skill.py`, accepts
      `Persona` or `PersonaConfig` (duck-typed via `.config`), TYPE_CHECKING
      imports only so no circular imports
- [x] Tests: conversation serialization round-trip with old files (defaults)
      → in `test/bond/test_skill.py` (helper precedence + old-JSON compat)

### Phase 4 — Tools

- [x] Create `src/bond/tools/skill_tools.py` with `load_skill` / `unload_skill`
  (use `context.conversation` / `context.persona`, mirror `memory_tools.py`)
- [x] Register builtin `PythonToolset("skills", [load_skill, unload_skill])`
  in `_default_toolsets` in `runtime.py`
- [x] `load_skill`: verify against effective available skills; error lists what
  IS available; append to `active_skills` (idempotent); return only a
  confirmation, NOT the skill content (content lives in the system prompt only;
  runtime imported function-locally to avoid a cycle with `runtime.py`)
- [x] `unload_skill`: remove from `active_skills`
- [x] Tests for allow/deny paths → `test/bond/tools/test_skill_tools.py`

### Phase 5 — System prompt sections

- [ ] `DefaultSystemMessageBuilder`: add `runtime` param + `include_skills` flag
- [ ] Render `<available-skills>` section (name + description lines)
- [ ] Render `<active-skills>` section (full SKILL.md blocks per active skill)
- [ ] Pass `include_skills=True` in generation builders (`mistral.py`,
  `ollama.py`); leave `False` for summarization / thought-condensation
- [ ] Lenient handling: unknown skill names in persona/conversation → warn, don't crash
- [ ] Tests for both sections (empty / populated / None-available fallback)

### Phase 6 — Docs & cleanup

- [ ] Update README "Future Features" section to reflect implemented state
- [ ] Docs note: skill cache is process-lifetime (restart to reload SKILL.md)
- [ ] Docs note: only enable skills you trust (future `tools/` will run in-process)

## Later phases (deliberately out of scope)

- [ ] Skill directories with `tools/*.py` (`EXPORT_TOOLS`) → `PythonToolset("skill:<name>")`
- [ ] `Toolbox.enable_toolset` / `disable_toolset` + live tool descriptions in
  `DefaultGenerationCapability` (currently snapshots `self._tools`)
- [ ] Toolbox skill-sync on persona switch in `_build_turn()`
- [ ] Skills popup in TUI (search/enable, reset → None, clear → [], select-all)
- [ ] `requirements.txt` per skill for dependency installation
- [ ] Free Form Memory (see README)