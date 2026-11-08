# Feature plan: skill-provided tools

## Overview (as implemented)

Skills (directories under `~/.config/bond/skills/<name>/` with a `SKILL.md`)
can optionally ship Python toolsets in `skills/<name>/tools/`. When a skill is
activated in a conversation (`load_skill`), its toolsets are added to the
agent loop's skill `Toolbox` under the prefix `sk:<skill-name>:`; when it is
deactivated (`unload_skill`), they are removed again. Tool files are discovered
and imported **lazily** — on first access of `Skill.toolsets` — and cached on
the `Skill` instance (which the runtime caches), so each skill imports its
tool files at most once.

**Deviation from the original design:** the toolbox does *not* live on the
`Conversation`. Instead, `AsyncAgentLoop` owns two toolboxes:
`_persona_toolbox` (rebuilt per persona via `persona.build_toolbox()`) and
`_skill_toolbox` (mutable). Before every turn, `_check_skill_toolsets()`
reconciles `_skill_toolbox` against `conversation.active_skills` (add missing,
remove stale, per-skill failure isolation) — the same "reconcile before use"
pattern regardless of who mutated `active_skills` (the `load_skill` tool, the
TUI popup, ...). Generation capabilities no longer receive a frozen
`list[Tool]` in the constructor; `generate()` takes a per-call
`tools: list[Tool] | None` parameter, which the loop fills with
`_get_available_tools()` (= persona tools + skill tools).

## Open questions / decisions

Asked the user; decisions taken:

1. **Where do skill toolsets live?** → On the `AsyncAgentLoop`'s mutable
   `_skill_toolbox` (not on the `Conversation`, not a separate internal set on
   the persona toolbox — see deviation note in Overview). Reconciled before
   every turn via `_check_skill_toolsets()`. Decided.
2. **Name collisions between skills / builtin tools?** → Prefix the toolset
   name and every tool name with `sk:<skill-name>:` at load time, via
   `PrefixedToolset` wrapping (pydantic `model_copy(update=...)`, originals
   not mutated). Decided.
3. **Which files count as tool files?** → Files directly in `tools/`
   (non-recursive, sorted) whose stem starts with `tool_` or ends with
   `_tool` / `_tools` (regex `_TOOL_FILE_RE`). Decided.
4. **Cache lifetime?** → On the `Skill` instance (`_toolsets` PrivateAttr);
   the runtime caches `Skill` objects, so no separate module-level cache is
   needed. (An earlier draft had `_toolset_cache` +
   `clear_skill_tools_cache()`; removed as redundant.) Decided.
5. **What does `load_skill` do?** → Loads only `SKILL.md` + a reference to the
   skill directory (`Skill.path`); the `tools/` dir is scanned only on first
   access of `Skill.toolsets`. Decided.
6. **How are toolsets exported from a tool file?** → A module-level
   `EXPORT_TOOLSETS` field, either an iterable of `Toolset`s or a callable
   returning one (so custom toolset types, e.g. MCP, can be exported too).
   Files without it are skipped (logged). Decided.
7. **Where does the toolbox live?** → On the `AsyncAgentLoop`, not on the
   `Conversation`. **Deviation from the original plan** (which put it on the
   conversation): the loop holds `_persona_toolbox` + `_skill_toolbox` and
   rebuilds/reconciles per turn. `Persona` is a plain dataclass with
   `toolsets: list[str]` + `runtime` and a `build_toolbox()` method; the
   toolbox is *not* built at persona construction.

## Design decisions (as implemented)

### 1. `Skill` gains a directory reference (`src/bond/skill.py`)

- Field is `path: Path | None = None` (plan said `dir`; implemented as `path`).
  `None` for static-environment skills → they never contribute toolsets.
- `Skill.load_from(skill_path, fallback_name) -> Result[Skill, str]` parses
  `SKILL.md` and sets `path`; `_parse_skill_md` now returns a
  `(name, description, instructions)` tuple (was: returned a `Skill`).
- `DynamicRuntimeEnvironment.load_skill` / `StaticRuntimeEnvironment.load_skill`
  and `BondRuntime.get_skill` all return `Result[Skill, str]` now (callers
  updated: CLI, TUI popup, `skill_tools`, system message builder).
- Lazy contract kept: parsing SKILL.md never touches `tools/`.

### 2. Lazy loader lives in `src/bond/skill.py` (not a separate module)

- `_load_skill_toolsets(skill_path, skill_name) -> list[Toolset]` (plan had a
  separate `src/bond/tools/skill_toolset.py` with `SkillToolset` — folded into
  `skill.py` instead).
- Discovery: `sorted((skill_path / "tools").glob("*.py"))` filtered by
  `_TOOL_FILE_RE = \A(tool_.+|.*_tools?)\.py\Z` (stem starts with `tool_` or
  ends with `_tool`/`_tools`; non-recursive).
- Import via `importlib.util.spec_from_file_location` under a unique module
  name `bond_skilltool_<skill>_<stem>`; `tools/` is inserted into `sys.path`
  via a context manager during the import so siblings can import each other.
- `EXPORT_TOOLSETS`: callable → called; iterable → used as-is; each item must
  be a `Toolset` else log + skip; missing attribute → log + skip; any import
  error → `logger.exception` + skip file; never propagates.
- Caching: on the `Skill` instance (`_toolsets` PrivateAttr, populated by the
  `toolsets` property). The runtime caches `Skill` objects, so no separate
  module-level cache. (Plan's `clear_skill_tools_cache` was removed as
  redundant.)

### 3. Prefixing at load time (`src/bond/tools/toolbox.py` + `skill.py`)

- `PrefixedToolset(Toolset)` wraps a toolset: name becomes `sk:<skill>:` +
  original name; `activate()` returns an `ActivePrefixedToolset` whose tools
  carry `model_copy(update=...)`-prefixed descriptions (originals not mutated).
  Execution routes through the original `BondTool.base_fn`; `release()`
  delegates to the wrapped active toolset.
- Prefixing happens in `_load_skill_toolsets` (wrap time), not in the toolbox —
  so `Toolbox`, `_do_tool_call`, and `_get_available_tools` only ever see
  prefixed names and needed no routing changes beyond `has_tool` checks.
- Deviation from plan: `add_skill_toolset` / `remove_skill_toolset` /
  `clear_skill_toolsets` / separate `_skill_toolsets` dict were *not*
  implemented — plain `add_toolset` / `remove_toolset` on one toolbox is
  enough because names are already prefixed.

### 4. Toolbox lives on `AsyncAgentLoop`, reconciled per turn

- **Deviation from plan** (plan: `Conversation` owns a lazy `toolbox` property
  + `sync_skill_toolsets()`). Implemented: the loop owns `_persona_toolbox`
  and a mutable `_skill_toolbox`, plus `_loaded_skill_toolsets:
  dict[str, set[str]]` bookkeeping (skill name → toolset names).
- `_check_skill_toolsets()` runs before every turn in `_run`: adds toolsets
  of newly active skills, removes toolsets of deactivated skills, per-skill
  try/except so one broken skill can't kill the loop; a skill is only
  recorded in `_loaded_skill_toolsets` after all its `add_toolset` calls
  succeed (retry next turn on failure).
- `_build_turn` prunes `active_skills` against the *new* persona's available
  skills (`prune_active_skills`) — uses the local `persona`, not `self.persona`.
- TUI (`command_handler._manage_skills_interactive`) mutates the conversation
  directly under `pause()`; there is no `set_active_skills` on the loop
  anymore — the per-turn check picks it up.

### 5. `Toolbox` became mutable (`src/bond/tools/toolbox.py`)

- New: `add_toolset(toolset)` (raises on duplicate toolset/tool name),
  `remove_toolset(name)` (silent no-op on unknown name, releases active
  toolset), `has_tool(name)`, `toolset_names`, `toolsets` properties.
- `tool_descriptions` kept (not renamed to `get_tools()`); `release()`
  unchanged in shape.
- Deviation: duplicate tool *names* raise `ValueError` instead of warn+skip
  (plan). Currently caught per-skill in `_check_skill_toolsets`.

### 6. `load_skill` / `unload_skill` (`src/bond/tools/skill_tools.py`)

- Handle the new `Result` from `get_skill` (Failure → error message).
- They only mutate `conversation.active_skills`; toolbox sync happens via the
  loop's per-turn `_check_skill_toolsets()` (deviation from plan's
  "conversation.sync_skill_toolsets() after every mutation").
- Plan's "(provides tools)" hint in the result message: **not yet implemented**.

### 7. Generation + behaviour paths pass tools per call

- `GenerationCapability.generate(conversation, triggers, callback, tools:
  list[Tool] | None, model_options=None)` — `tools` is a per-call parameter.
- `DefaultGenerationCapability` / `MistralGeneration` dropped the `tools`
  constructor arg and use `tools or []` at the endpoint call.
- `Provider.generation()` protocol and mistral/ollama implementations dropped
  the `toolbox` parameter; `PersonaConfig.instantiate()` no longer builds a
  toolbox; `Persona` is a dataclass with `toolsets: list[str]` + `runtime`
  and a `build_toolbox()` method (built per turn in `_build_turn`).
- `AsyncAgentTurn.run(..., tools)` passes tools through to
  `generate()`; `AsyncAgentLoop._run` calls
  `turn.run(conversation, signal, self._get_available_tools())`.
- Tool execution in the loop: `_do_tool_call(persona_toolbox, skill_toolbox,
  function_call, context)` routes persona-toolbox first, then skill toolbox,
  else `Failure("Unknown tool name: ...")`.
- Endpoint protocol (`chat_completions.py`) unchanged — still takes
  `tools: list[Tool]`.

### 8. Tests — **mostly broken, not yet updated**

- `test_skill.py`: imports removed `parse_skill_md`, asserts `Skill` where
  `Result` is returned now, constructs `Persona(toolbox=...)` (field gone).
- `test_skill_tools.py` / `test_default_system_message_builder.py`: mock
  `get_skill` returning raw `Skill` (now needs `Result`); `Persona(...)`
  construction missing `toolsets`/`runtime`.
- Still needed: `test_skill_toolset.py`-equivalent tests for
  `_load_skill_toolsets` (discovery filter, `EXPORT_TOOLSETS` iterable vs
  callable, broken file skipped, sibling import, caching on instance) and
  `PrefixedToolset` (prefixed names, routing to original tool, release).

### 9. Docs

- `docs/skills.md` "Skill tools" section: **not yet written**.
- Module docstrings of `skill.py` / `toolbox.py`: partially updated.

## Task list

- [x] `src/bond/skill.py`: `Skill.path`, lazy `toolsets` property, `load_from`, `_load_skill_toolsets` + discovery/import/prefix helpers
- [x] `src/bond/runtime.py`: env + runtime `load_skill`/`get_skill` return `Result[Skill, str]`
- [x] `src/bond/tools/toolbox.py`: `PrefixedToolset`/`ActivePrefixedToolset`, mutable `add_toolset`/`remove_toolset`, `has_tool`, `toolset_names`, `toolsets`
- [x] `src/bond/behaviours/async_loop.py`: `_skill_toolbox` + `_loaded_skill_toolsets`, per-turn `_check_skill_toolsets()`, `_get_available_tools()` passed to `turn.run`, `_do_tool_call` routing, prune in `_build_turn`
- [x] `src/bond/behaviours/async_turn.py`: `run(..., tools)` passthrough
- [x] `src/bond/capabilities/generation.py` + general/mistral generation: per-call `tools` param
- [x] `src/bond/persona.py` + `providers/provider.py` + mistral/ollama: drop toolbox from persona/provider construction; `Persona.build_toolbox()`
- [x] `src/bond/tools/skill_tools.py` + `cli/bond.py` + `tui/command_handler.py` + system message builder: handle `Result` from `get_skill`
- [ ] `load_skill` result message: "(provides tools)" when `skill.path/tools` exists
- [x] Add `test/bond/tools/test_toolbox.py`: `ActiveToolset`, `PythonToolset`,
      `Toolset` ABC, `prefix_tool_description`, `PrefixedToolset` /
      `ActivePrefixedToolset` (prefixing, routing, release delegation), and
      `Toolbox` (construction, duplicate handling, add/remove, release +
      lazy re-activation, `call_tool` result/exception mapping)
- [x] Add `test/bond/tools/test_skill_toolsets.py`: discovery filter, loading +
      `sk:` prefixing, `EXPORT_TOOLSETS` iterable/callable/missing/invalid,
      broken/crashing/non-UTF8/`sys.exit` tool files contained, sibling imports
      + `sys.path` restoration, per-`Skill`-instance caching + reimport on new
      instance, runtime-level caching, `PrefixedToolset` behavior, Toolbox
      add/call/remove + cross-skill name collisions
- [x] Fix old tests: `test_skill.py` (`parse_skill_md` → `_parse_skill_md` tuple,
      `env.load_skill`/`get_skill` now return `Result` — unwrap/`Failure`
      assertions, `Persona(toolsets=..., runtime=...)` instead of `toolbox=`),
      `test_skill_tools.py` (same `Persona` fix, `get_skill` mocks return
      `Result.from_value(...)`, runtime-failure test uses `Failure(...)`),
      `test_default_system_message_builder.py` (`get_skill` mocks return
      `Success(...)` — builder checks `isinstance(skill, Success)`)
- [ ] `docs/skills.md` "Skill tools" section + docstrings
- [ ] Run full test suite; verify no regressions
