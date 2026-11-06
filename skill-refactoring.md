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
- **Skills (new)**: `~/.config/bond/skills/<name>/SKILL.md` with `---
  name / description ---` frontmatter (parsed manually, no yaml dependency).
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
  `conversation.active_skills`, and returns the full skill content as the tool
  result (visible same-turn). `unload_skill` removes from `active_skills`.
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

- [ ] Rename `~/.config/bond/skills/` → `prompts/` in `DynamicRuntimeEnvironment`
- [ ] Rename env ABC + both implementations + runtime methods:
      `list_skills`/`load_skill`/`get_skill` → `list_prompts`/`load_prompt`/`get_prompt`
- [ ] Rename runtime cache `_loaded_skills` → `_loaded_prompts`
- [ ] Rename `resolve_skills` → `resolve_prompts` in `util.py`, macro `{SKILL:x}` → `{PROMPT:x}`
- [ ] Update call sites: `generation.py`, `summarization.py`,
      `thought_condensation.py`, `tool_loop_runner.py`
- [ ] Update `test/bond/providers/general/util/test_tool_loop_runner.py`
      (mocks + `{SKILL:...}` strings)
- [ ] Decide migration story for existing users' `skills/` dir
      (auto-migrate on startup vs. docs note)

### Phase 2 — Skill model + runtime API

- [ ] Create `src/bond/skill.py`: `Skill` pydantic model + `parse_skill_md()`
- [ ] Add `list_skills()` / `load_skill(name) -> Skill` to `RuntimeEnvironment` ABC
- [ ] `StaticRuntimeEnvironment`: accept `skills: dict[str, Skill]`
- [ ] `DynamicRuntimeEnvironment`: `list_skills()` globs `skills/*/SKILL.md` dirs;
      `load_skill` reads + parses `skills/<name>/SKILL.md`
- [ ] `BondRuntime`: `list_skills()`, `get_skill()` with `_loaded_skills` cache
- [ ] Tests for the SKILL.md frontmatter parser (incl. fallback name)

### Phase 3 — Data model: conversation + persona fields

- [ ] `Conversation`: add `available_skills: list[str] | None = None`,
      `active_skills: list[str] = []`
- [ ] `PersonaConfig`: add `available_skills: list[str] = []`
- [ ] Add `effective_available_skills(conversation, persona)` helper (single
      source of truth for tool + builder)
- [ ] Tests: conversation serialization round-trip with old files (defaults)

### Phase 4 — Tools

- [ ] Create `src/bond/tools/skill_tools.py` with `load_skill` / `unload_skill`
      (use `context.conversation` / `context.persona`, mirror `memory_tools.py`)
- [ ] Register builtin `PythonToolset("skills", [load_skill, unload_skill])`
      in `_default_toolsets` in `runtime.py`
- [ ] `load_skill`: verify against effective available skills; error lists what
      IS available; append to `active_skills` (idempotent); return full content
- [ ] `unload_skill`: remove from `active_skills`
- [ ] Tests for allow/deny paths

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
