# Feature plan: skill-provided tools

## Overview

Skills (directories under `~/.config/bond/skills/<name>/` with a `SKILL.md`)
can optionally ship Python toolsets in `skills/<name>/tools/`. When a skill is
activated in a conversation (`load_skill`), its toolsets are added to the
conversation's `Toolbox` under the prefix `sk:<skill-name>:`; when it is
deactivated (`unload_skill`), they are removed again. Tool files are discovered
and imported **lazily** — only when the toolbox resolves tools — and cached for
the lifetime of the skill (until unload / cache clear).

Each `Conversation` owns its own `Toolbox` (a pydantic `PrivateAttr`, so it is
not serialized). The persona and the active skills only *provide* toolsets; the
conversation aggregates them and manages adding/removing on the go. This avoids
the nasty side effect of several conversations mutating the one shared,
runtime-singleton persona toolbox. Generation capabilities stop receiving a
frozen `list[Tool]`; in `generate()` they ask the conversation:
`conversation.toolbox.get_tools()`.

## Open questions / decisions

Asked the user; decisions taken:

1. **Where do skill toolsets live?** → In a separate internal set
   (`_skill_toolsets`) on the `Toolbox`, so `clear_skill_toolsets()` never
   touches persona-defined toolsets. Decided.
2. **Name collisions between skills / builtin tools?** → Prefix the toolset
   name and every tool name with `sk:<skill-name>:`. Decided.
3. **Which files count as tool files?** → Files directly in `tools/`
   (non-recursive, sorted) whose stem starts with `tool_` or ends with
   `_tool` / `_tools`. Decided.
4. **Cache lifetime?** → Lives as long as the skill is loaded; manual
   `clear_skill_tools_cache()` for tests. Decided.
5. **What does `load_skill` do?** → Loads only `SKILL.md` + a reference to the
   skill directory (`Skill.dir`); the `tools/` dir is scanned only on
   `get_tools()`. Decided.
6. **How are toolsets exported from a tool file?** → A module-level
   `EXPORT_TOOLSETS` field, either an iterable of `Toolset`s or a callable
   returning one (so custom toolset types, e.g. MCP, can be exported too).
   Files without it are skipped. Decided.
7. **Where does the toolbox live?** → On the `Conversation` (as a
   `PrivateAttr`, excluded from the pydantic model). The persona only provides
   toolset *names* (`PersonaConfig.toolsets`); each active skill provides a
   lazily loaded `SkillToolset`. The conversation's `toolbox` property builds
   and caches the `Toolbox`, rebuilds when `conversation.persona` changes, and
   `sync_skill_toolsets()` reconciles skill toolsets with `active_skills`.
   Decided (replaces the earlier shared-persona-toolbox approach, which let
   different conversations mutate the same runtime-singleton persona).

## Design decisions

### 1. `Skill` gains a directory reference (`src/bond/skill.py`)

- Add field `dir: Path | None = None` to `Skill` (the skill's directory;
  `None` for static-environment skills). Not part of SKILL.md;
  `render_skill_md` / `parse_skill_md` unchanged.
- `DynamicRuntimeEnvironment.load_skill` (`src/bond/runtime.py:314`) sets
  `skill.dir = self._config_dir / "skills" / name` after parsing.
- `StaticRuntimeEnvironment.load_skill` leaves it `None` → such skills simply
  never contribute toolsets.
- Rationale: keeps the lazy contract — parsing SKILL.md never touches
  `tools/`.

### 2. New lazy loader: `src/bond/tools/skill_toolset.py`

- `load_skill_toolsets(skill_name: str, skill_dir: Path) -> list[Toolset]`
  with a module-level cache `_cache: dict[str, list[Toolset]]` keyed by
  `skill_name`, plus `clear_skill_tools_cache(skill_name: str | None = None)`
  (None clears all — used by tests).
- Discovery: `sorted((skill_dir / "tools").glob("*.py"))`, keep files whose
  stem matches `tool_*` or `*_tool` / `*_tools`.
- Import each file with `importlib.util.spec_from_file_location` under a unique
  module name (`bond_skilltool_<skill>_<stem>`); the `tools/` dir is inserted
  into `sys.path` (via a context manager) during the import so sibling modules
  import each other.
- Read `EXPORT_TOOLSETS` from the module: if callable → call it; if iterable →
  use as-is; each item must be a `Toolset`, else log + skip. Missing attribute
  → debug log + skip. Any exception while importing/reading a file →
  `logger.error` with traceback and skip that file; never propagate.
- `class SkillToolset(Toolset)`: constructed with `skill_name` and `skill_dir`;
  `activate()` returns an `ActiveSkillToolset` that resolves the (cached)
  toolsets on first use and activates each one. `tool_descriptions` property
  activates lazily as well so `Toolbox` can list tools without executing them.

### 3. Prefixing (`src/bond/tools/toolbox.py`)

- `PrefixedToolset(Toolset)`: wraps a toolset and prefixes its `name` with
  `sk:<skill>:` and each tool description's `function.name` with the same
  prefix (via `model_copy(update=...)` on the pydantic `Tool` model, so the
  original objects are not mutated). Tool *execution* is routed through the
  original (unprefixed) tool inside the wrapped active toolset.
- Prefixing happens in `Toolbox.add_skill_toolset(toolset, skill_name)` —
  i.e. at add time, not read time — so descriptions and `call_tool` always see
  the same prefixed names.
- Alternative considered: prefix only inside `get_tools()`. Rejected: then
  `call_tool` would need a second name-mapping pass and the two views could
  drift.

### 4. `Conversation` owns the toolbox (`src/bond/conversation/conversation.py`)

- New `PrivateAttr`: `_toolbox: Toolbox | None = None` and
  `_toolbox_persona: str | None = None` (persona the toolbox was built for).
- `toolbox` property (lazy): if `_toolbox` is None or
  `_toolbox_persona != self.persona`, rebuild: resolve
  `runtime.get_persona(self.persona)` → `config.toolsets` (names) →
  `runtime.build_toolbox(names)` (existing `BondRuntime.build_toolbox`,
  `runtime.py:452`), then add a `SkillToolset` for every active skill that
  has a `dir` with a `tools/` subdir, and cache as `_toolbox`.
  Function-local `from bond.runtime import BondRuntime` (circular-import safe,
  same pattern as `skill_tools.py` / `default_system_message_builder.py`).
  If `self.persona` is None → empty `Toolbox([])`.
- `sync_skill_toolsets()` method on `Conversation`: reconciles the toolbox's
  skill toolsets with `self.active_skills` — removes toolsets of skills no
  longer active (and `clear_skill_tools_cache(name)` for them), adds
  `SkillToolset`s for newly active skills with a `tools/` dir. Called after
  every mutation of `active_skills`.
- Rationale: personas become pure value objects (no mutable toolbox on the
  runtime singleton); each conversation gets an isolated toolbox. Alternative
  considered: syncing skill toolsets into the persona's shared toolbox —
  rejected because conversations of the same persona would contaminate each
  other.

### 5. `Toolbox` becomes mutable (`src/bond/tools/toolbox.py`)

- New internal state: `_skill_toolsets: dict[str, Toolset]` (key = prefixed
  toolset name, e.g. `sk:pdf:extract`) alongside the existing `_toolsets` /
  `_active_toolsets` (base/persona toolsets).
- New methods:
  - `add_toolset(toolset)` / `remove_toolset(name)` — generic add/remove for
    base toolsets (used by the conversation when rebuilding).
  - `add_skill_toolset(toolset: Toolset, skill_name: str)` — wraps in
    `PrefixedToolset`, activates, registers in `_skill_toolsets`; on a
    duplicate prefixed tool name logs a warning and skips the colliding tool
    (does not raise).
  - `remove_skill_toolset(name)` — removes + `release()`s the active toolset.
  - `clear_skill_toolsets()` — removes all skill toolsets (base toolsets
    untouched).
  - `get_tools() -> list[Tool]` — recomputed on every call: base toolsets'
    descriptions + all skill toolsets' descriptions (prefixed). Replaces the
    frozen `_all_tool_descriptions`.
  - `call_tool(...)` — `_find_tool` also looks into skill toolsets.
- `tool_descriptions` property kept as a deprecated alias for `get_tools()`
  (existing tests keep working); `release()` now also releases skill toolsets.

### 6. Wiring in `load_skill` / `unload_skill` (`src/bond/tools/skill_tools.py`)

- After mutating `conversation.active_skills`, call
  `conversation.sync_skill_toolsets()` (no toolbox argument needed anymore —
  the conversation owns it).
- `prune_active_skills` call sites (`src/bond/tui/command_handler.py:263`) call
  `conversation.sync_skill_toolsets()` after pruning.
- `load_skill`'s return message gains `(provides tools)` when
  `skill.dir is not None and (skill.dir / "tools").is_dir()` — a cheap
  `stat`, no import.

### 7. Generation + behaviour paths use `conversation.toolbox`

- `DefaultGenerationCapability` / `MistralGeneration`
  (`src/bond/providers/general/generation.py`, `src/bond/providers/mistral/generation.py`):
  drop the `tools: list[Tool]` constructor arg; in `generate()` compute
  `tools = conversation.toolbox.get_tools()` right before calling the endpoint.
- `Provider.generation()` protocol (`src/bond/providers/provider.py`) and the
  mistral/ollama implementations drop the `toolbox` parameter
  (`mistral.py:83-91`, `ollama.py:82-93`); `PersonaConfig.instantiate()`
  (`persona.py:143-189`) no longer builds a toolbox, and `Persona` drops the
  `toolbox` field.
- Behaviours use the conversation's toolbox for execution:
  `single_turn.py:121,127` and `async_loop.py:283,291` call
  `conversation.toolbox.call_tool(...)` instead of `self._persona.toolbox`.
  (`SingleTurn.run` / `_handle_tool_calls` already have the conversation.)
- `ToolCallLoop` (`src/bond/providers/general/util/tool_call_loop.py:51`) uses
  `self._toolbox.get_tools()` per iteration; `ToolLoopRunner` keeps its own
  private task-list toolbox — unchanged.
- The endpoint protocol (`src/bond/endpoints/chat_completions.py`) keeps
  `tools: list[Tool]` — only the capability/loop layer changes.
- Rationale: `generate()` receives the `conversation`, and `get_tools()` is
  cheap (cached loader), so tools added by `load_skill` mid-conversation are
  visible from the very next model call, and removed ones disappear on unload —
  per conversation, without touching the persona.

### 8. Tests

- New `test/bond/tools/test_skill_toolset.py`: discovery filters
  (`tool_x.py` yes, `x_tool.py` yes, `x_tools.py` yes, `helper.py` no,
  subdirs ignored), `EXPORT_TOOLSETS` as iterable and as callable, custom
  `Toolset` subclass passes through, missing `EXPORT_TOOLSETS` skipped, broken
  file logged + skipped, sibling import works, cache returns identical list on
  second call, `clear_skill_tools_cache` forces reload.
- New `test/bond/tools/test_toolbox.py`: add/remove/clear skill toolsets;
  `get_tools()` includes prefixed skill tools only while added; `call_tool`
  routes `sk:pdf:...` to the skill tool; duplicate name skipped with warning;
  `clear_skill_toolsets()` leaves base toolsets intact; `tool_descriptions`
  alias == `get_tools()`.
- Extended `test/bond/conversation/test_conversation.py`: `conv.toolbox` is a
  `PrivateAttr` (not serialized), lazy-builds from persona toolset names +
  active skills via a mocked runtime, rebuilds when `persona` changes,
  empty toolbox when `persona` is None, `sync_skill_toolsets()` adds/removes
  skill toolsets on `active_skills` changes and evicts their cache.
- Extended `test/bond/tools/test_skill_tools.py`: `load_skill` with a skill
  that has `dir` + `tools/` adds a `SkillToolset` to `conversation.toolbox`;
  `unload_skill` removes it and evicts the cache; skill without `dir` adds
  nothing; result message contains "provides tools" only when applicable.
- Extended generation tests (`test/bond/providers/general/...`): capability
  built without a tools list; `generate()` sends
  `conversation.toolbox.get_tools()` to the mocked endpoint; adding a skill
  toolset to the conversation between calls changes the next request's tools.
- Update `test/bond/providers/general/util/test_tool_call_loop.py` /
  `test_tool_loop_runner.py` and persona/provider construction sites that pass
  a toolbox into `generation()` / `Persona(...)`.

### 9. Docs

- `docs/skills.md`: new "Skill tools" section — layout
  (`skills/<name>/tools/tool_*.py`), the `EXPORT_TOOLSETS` contract
  (iterable or callable returning `Toolset`s), the `sk:<name>:` prefix,
  lazy loading + cache semantics, removal on unload.
- Module docstrings of `src/bond/skill.py` and `src/bond/tools/toolbox.py`
  updated to mention tool dirs / skill toolsets.

## Task list

- [ ] `src/bond/skill.py`: add `dir: Path | None = None` to `Skill`; docstring note
- [ ] `src/bond/runtime.py`: `DynamicRuntimeEnvironment.load_skill` sets `skill.dir`
- [ ] `src/bond/tools/skill_toolset.py` (new): cache + `load_skill_toolsets` +
      `clear_skill_tools_cache` + `SkillToolset`/`ActiveSkillToolset`
- [ ] `src/bond/tools/toolbox.py`: `PrefixedToolset`, `_skill_toolsets`,
      generic `add_toolset` / `remove_toolset`,
      `add_skill_toolset` / `remove_skill_toolset` / `clear_skill_toolsets`,
      `get_tools()`, `call_tool` routing, `tool_descriptions` alias, `release()`
- [ ] `src/bond/conversation/conversation.py`: `_toolbox` PrivateAttr, lazy
      `toolbox` property (persona toolset names + active skill toolsets,
      rebuild on persona change), `sync_skill_toolsets()`
- [ ] `src/bond/tools/skill_tools.py`: call `conversation.sync_skill_toolsets()`
      in `load_skill` / `unload_skill` + "(provides tools)" in result message
- [ ] `src/bond/tui/command_handler.py`: call `conversation.sync_skill_toolsets()`
      after `prune_active_skills`
- [ ] `src/bond/persona.py` + `src/bond/providers/provider.py`: drop the
      toolbox from `Persona` / `PersonaConfig.instantiate()` /
      `Provider.generation()`
- [ ] `src/bond/providers/general/generation.py` + `mistral/generation.py`:
      drop `tools` arg, use `conversation.toolbox.get_tools()` in `generate()`
- [ ] `src/bond/providers/mistral/mistral.py` + `ollama/ollama.py`: update
      `generation()` calls
- [ ] `src/bond/behaviours/single_turn.py` + `async_loop.py`: execute via
      `conversation.toolbox.call_tool(...)`
- [ ] `src/bond/providers/general/util/tool_call_loop.py`: use `get_tools()`
- [ ] Tests: new `test_skill_toolset.py`, new `test_toolbox.py`, extend
      `test_conversation.py`, `test_skill_tools.py`, generation + tool-call-loop
      tests, and persona/provider construction sites
- [ ] `docs/skills.md` + docstrings updated
- [ ] Run full test suite; verify no regressions in existing tool tests
