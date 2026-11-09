# Feature plan: local `.bond` directory

## Overview

A project-local `.bond/` directory lets a project extend the runtime with its
own skills, runnable scripts, and a local conversation store — without
touching the global `~/.config/bond` / `~/.local/share/bond` config.

Proposed layout:

```
.bond/
  skills/<name>/SKILL.md        # local skills (+ optional tools/), same format as global
  scripts/                      # scripts the agent may run via the dedicated `local` toolset
  conversations/                # target of the new `lsave` / `local-save` command
```

**Discovery rule** (as requested): the `.bond` directory is looked up in the
current working directory or any parent of it. If several parents have one,
only the **closest** one is used — no merging across levels.

## Open questions / decisions

Asked the user; decisions taken:

1. **Scope** → only skills, scripts, conversations. No local `config.json`, no
   local personas. Decided.
2. **Toggle** → `initialize_dynamic(..., disable_local_config: bool = False)`
   (and the same flag on `initialize_static` for symmetry). When set, every
   local lookup returns `None` / empty, as if no `.bond` existed. Decided.
3. **`lsave` without a `.bond` directory** → does nothing except a small
   notification ("local saving can't be done without a `.bond` directory").
   It must **not** create `.bond`. Decided.
4. **Scripts must not go through the shell toolset** → dedicated builtin
   `local` toolset with `list_local_scripts` + `run_local_script` that only
   ever executes files directly inside `.bond/scripts/`, via `subprocess`
   with `shell=False` (no shell injection). The shell gate
   (`allow_shell_commands` in `async_loop.py`) does not apply to it — a
   persona can enable `"local"` without `"shell"`. Decided.
5. **File tools must not modify anything inside a `.bond` directory** →
   hard deny in the mutating file tools, for *any* `.bond` path component
   (not just the currently discovered one), mirroring the existing `.git`
   rule. Decided.

6. **`run_local_script` never asks for confirmation** — not in interactive
   mode either. Local scripts are made for the agent to call on its own; the
   user-controlled allowlist (`.bond/scripts/`) is the safety boundary, so
   no per-call confirmation. Decided.
7. **`lload` / `local-load` command** — added alongside `lsave`, mirroring
   `load` but reading from `.bond/conversations/`, with the same no-`.bond`
   guard + notification. Decided.
8. **CLI flags** → `--disable-local-config` on `talk` / `chat` / `ask`,
   threaded into `initialize_dynamic`. Decided (no longer optional).

## Design decisions

### 1. Discovery — new module `src/bond/local.py`

- `LOCAL_DIR_NAME = ".bond"`
- `find_local_bond_dir(start: Path | None = None) -> Path | None`: walks
  `start` (default `Path.cwd()`) and each parent upward, returns the first
  ancestor that is a directory containing a `.bond/` subdirectory.
  Closest wins; no merging.
- Computed on each call from `Path.cwd()`, so it follows `:cd` in the TUI
  (the TUI's `:cd` does `os.chdir`) — provided the `ToolCallContext.cwd`
  handed to tools is kept fresh; see section 7 for the currently suspected
  stale-cwd bug and its fix.

### 2. Runtime integration — `src/bond/runtime.py`

The local dir is cwd-based, not config-dir-based, so it lives on
`BondRuntime`, not on `RuntimeEnvironment`:

- `initialize_dynamic(config_dir=None, data_dir=None, enable_plugins=True,
  disable_local_config=False)` and `initialize_static(..., disable_local_config=False)`
  store the flag on the runtime.
- `get_local_bond_dir() -> Path | None` — `None` if disabled, else
  `find_local_bond_dir(Path.cwd())`.
- `get_local_skills_path() / get_local_scripts_path() / get_local_conversations_path()`
  → `bond_dir / "skills" | "scripts" | "conversations"`, or `None` when no
  bond dir.
- **Skills**: `BondRuntime.list_skills()` returns local ∪ global skill names
  (local names shadow global ones on collision). `BondRuntime.get_skill(name)`
  checks `.bond/skills/<name>/SKILL.md` first via the existing
  `Skill.load_from(path, fallback_name=name)`, falls back to
  `env.load_skill(name, ...)`. Local skills get the usual `sk:<name>:`
  prefix and their `tools/` work unchanged (`_load_skill_toolsets` in
  `skill.py` already handles arbitrary paths).

### 3. Script tools — new `src/bond/tools/local_tools.py`, registered as `PythonToolset("local", ...)` in `_default_toolsets`

- `list_local_scripts()` → lists regular files directly in
  `.bond/scripts/` (non-recursive) with a one-line description taken from a
  leading `# ...` comment. Error message if no `.bond` / no `scripts/` dir.
- `run_local_script(script_name: str, args: list[str] = [], timeout: int = 60)`:
  - Requires a local bond dir; rejects names containing `/`, `\`, or `..`;
    resolves `(scripts_dir / name).resolve()` and requires the resolved
    parent to be exactly the resolved scripts dir (no traversal) and the
    target to be a regular file.
  - Interpreter choice: executable bit set → run the file directly;
    `.py` → `sys.executable`; `.sh` → `sh`; otherwise try direct exec.
  - `subprocess.run([interpreter..., script, *args], shell=False,
    capture_output=True, text=True, timeout=timeout, cwd=bond_dir.parent)`.
  - **No confirmation, ever** — the script runs directly in both interactive
    and non-interactive mode (decision 6: `.bond/scripts/` is the user's
    explicit allowlist).
  - Returns exit code + last 50 lines of stdout/stderr; `TimeoutExpired` →
    clear error message.
  - **Not** gated by `allow_shell_commands()` — the persona opting into the
    `"local"` toolset is the gate.

### 4. Write protection — `src/bond/tools/file_system/util.py` + mutating tools

- `path_is_in_bond(path) -> bool`: any path component == `.bond` (same style
  as existing `path_is_in_git`).
- `check_write_access(context, path) -> tuple[bool, str]`: runs the normal
  `check_access`, then hard-denies if `path_is_in_bond(path)` ("permission
  denied: `.bond` directories are read-only for tools").
- `create_file.py`: switch `check_access` → `check_write_access`.
- `apply_patch.py`: reject patch blocks targeting a `.bond` path right next
  to the existing `path_is_in_git` check (it currently has no `check_access`
  call, so this is a deny block, not a wrapper).
- Read-only tools (`read_file`, `search_file`, `grep`, `list_directory`,
  pdf tools) are unchanged — reading `.bond` stays allowed.
- Trusted code paths (the `lsave` command, runtime internals) may still
  write into `.bond/conversations` — only agent tools are blocked.

### 5. `lsave` / `local-save` and `lload` / `local-load` commands — TUI + CLI

- `src/bond/tui/command_handler.py` and `src/bond/cli/_interactive.py`: new
  `lsave` (aliases `local-save`) and `lload` (aliases `local-load`) parser
  entries, each with an optional `name` argument.
  - `lsave` mirrors `save`: name given → `move_to(name, local_path)`, else
    `save_as(conv.name, local_path)`, else "please specify a name".
  - `lload` mirrors `load`: `Conversation.load(name, local_path)` +
    `set_conversation`; without a name, the TUI launches its interactive
    conversation picker pointed at the local path.
- Guard (both commands): if `runtime.get_local_conversations_path()` is
  `None` (no `.bond` found or `disable_local_config`) → notify
  "Local saving can't be done without a `.bond` directory" (for `lsave`) /
  the analogous message for `lload`, and return.
  **Never creates `.bond`** — only writes into/reads from the existing
  `.bond/conversations/` (created as a subdir of an existing `.bond`, which
  is fine).

### 6. Entry points

Thread `--disable-local-config` through `tui/main.py`, `cli/chat.py`,
`cli/ask.py` → `run_interactive_session(...)` → `initialize_dynamic(...)`.

### 7. Known issue to check & fix separately: stale `cwd` in `ToolCallContext`

**Suspected bug (to be verified in a separate step):** `ToolCallContext`
captures `Path(os.getcwd())` once at creation time (`ToolCallContext.default`
/ `async_default` in `tools/tool.py`; created e.g. in `tui/main.py:58`,
`cli/_interactive.py:400`, `cli/ask.py:73`). The TUI `:cd` command
(`tui/command_handler.py` `_handle_shell_command`) only calls `os.chdir()`
and never updates the context. `AsyncAgentLoop._build_turn()` already
refreshes `persona`/`conversation` on the context per turn
(`behaviours/async_loop.py`, the block marked "dirty hack") and
`_run()` calls `_check_skill_toolsets()` before every turn — but **never
refreshes `cwd`**. So after `:cd`, all tools keep operating on the directory
the app was started in.

**Intended behaviour:** tools called from the loop always receive the fresh
cwd via `ToolCallContext`.

**Planned fix:** in `AsyncAgentLoop._run()`, right after
`self._check_skill_toolsets()` and before `self._agent_turn.run(...)`, add
`self._tool_call_context.cwd = Path(os.getcwd())` (needs `import os` /
`from pathlib import Path` as required). Also audit the other context creation
sites (`providers/general/util/tool_loop_runner.py` passes `cwd=None` —
check whether that path also needs the fresh cwd). Add a regression test that
`chdir`s between turns and asserts the context passed to tools reflects the
new cwd.

## Deviations / changes during implementation

- **CLI `save`/`lsave` no longer fall back to the session's default conv name**:
  `cmd_save` in `cli/_interactive.py` used to save an unnamed conversation under
  `self._conv_name` (e.g. "last-conv"). Now, if no `name` argument is given and
  `conv.name is None`, both `cmd_save` and `cmd_lsave` print "Please specify a
  name for the conversation to save" and do nothing (matches the TUI `save`
  behavior). The automatic save-on-exit under `conv_name` in
  `run_interactive_session` is unchanged. User-reported pre-existing bug.

## Task list

- [x] `src/bond/local.py`: `LOCAL_DIR_NAME`, `find_local_bond_dir()` (closest ancestor wins, no merge)
- [x] `src/bond/runtime.py`: `disable_local_config` param on `initialize_dynamic` + `initialize_static`; `get_local_bond_dir()` + `get_local_{skills,scripts,conversations}_path()`; local-first skill merge in `list_skills()` / `get_skill()` (local skills cached by absolute path in `_local_skill_cache` so `:cd` between projects resolves same-named skills correctly; global skills keep the existing name cache)
- [x] **Separate step — verify & fix the stale-cwd bug** (section 7): confirmed in code (`ToolCallContext.default`/`async_default` capture `Path(os.getcwd())` once; `:cd` only does `os.chdir`; `_run` never refreshed cwd). Fixed in `AsyncAgentLoop._run()`: `self._tool_call_context.cwd = Path(os.getcwd())` after `_check_skill_toolsets()`, before `self._agent_turn.run(...)`. Audit of `tool_loop_runner.py`: its `cwd=None` is intentional (filesystem disabled for that internal runner) — no change. Regression test still to add under Tests.
- [ ] `src/bond/local.py`: `LOCAL_DIR_NAME`, `find_local_bond_dir()` (closest ancestor wins, no merge)
- [ ] `src/bond/runtime.py`: `disable_local_config` param on `initialize_dynamic` + `initialize_static`; `get_local_bond_dir()` + `get_local_{skills,scripts,conversations}_path()`; local-first skill merge in `list_skills()` / `get_skill()`
- [x] `src/bond/tools/local_tools.py`: `list_local_scripts` + `run_local_script` (path validation incl. symlink-escape check, interpreter choice, `shell=False`, timeout, **no confirmation**); registered as `PythonToolset("local", ...)` in `_default_toolsets` in `runtime.py`
- [x] `src/bond/tools/file_system/util.py`: `path_is_in_bond()` (any `.bond` path component) + `check_write_access()` (normal access check, then hard deny inside `.bond`); wired into `create_file.py` (replaces `check_access`) and `apply_patch.py` (deny block next to the `.git` check); tool descriptions mention `.bond` read-only. Read tools unchanged; trusted paths (lsave/lload, runtime) can still use `.bond/conversations`
- [x] `src/bond/tui/command_handler.py`: `lsave` / `local-save` and `lload` / `local-load` with no-`.bond` guard + warning notification; refactored `_load_conversation_interactive` / `_list_conversations` to take a base path and added `_load_conversation_by_name` helper shared by `load`/`lload`
- [x] `src/bond/cli/_interactive.py`: `cmd_lsave` / `cmd_lload` (+ parser entries with `local-save` / `local-load` aliases) with the same guard
- [x] Entry points: `--disable-local-config` flag on `talk` (`tui/main.py`), `chat` (`cli/chat.py`), `ask` (`cli/ask.py`) threaded to `initialize_dynamic`; also added to `followup` (`cli/followup.py`, the other `run_interactive_session` caller) via a new `disable_local_config` param on `run_interactive_session` (default `False`, so existing callers are unaffected)
- [x] Tests written (suite run left to the user per workflow): `test/bond/test_local.py` (discovery closest-wins/parent/none/file-start, disable flag, local skills shadow global + not listed when disabled, path-keyed cache across projects); `test/bond/tools/test_local_tools.py` (toolset registered, listing incl. descriptions, invalid-name/traversal/symlink rejection, real .py/.sh/executable runs with args, exit-code + stderr capture, timeout, runs in project root, missing `.bond`/scripts dir); `test/bond/tools/test_bond_write_protection.py` (`path_is_in_bond`, `check_write_access`, `create_file`/`apply_patch` into `.bond` denied, normal paths ok, reads in `.bond` allowed); `test/bond/test_local_commands.py` (lsave/lload guards in CLI `_CommandHandler` and TUI `TuiCommandHandler`); `test/bond/behaviours/test_cwd_refresh.py` (stale-cwd regression: cwd refreshed per turn)
- [ ] Docs: new `docs/local-bond-dir.md` (layout, discovery rule, `disable_local_config`, `lsave`/`lload`, script tools with no-confirmation behavior, write protection, cwd behavior); short pointer in `docs/skills.md` that local skills shadow global ones
- [ ] Run full test suite; verify no regressions (user-run per workflow). First run had 8 failures, all test-side bugs (now fixed): cache test needed an initialized runtime env (uses `runtime_env` fixture); lsave assertions now check `<name>_metadata.json`/`<name>_episodes.json` (conversations are flat files, not subdirs); lload tests seed a real conversation via `Conversation().save_as` since `exists` needs both files; write-protection tests must `mkdir` the `.bond` parent before writing the fixture file
