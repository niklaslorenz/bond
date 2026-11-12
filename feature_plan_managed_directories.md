# Feature plan: persona-managed directories (`bond://` URIs)

## Overview

Give each persona a configurable list of **managed directories** — dedicated
folders the agent can always access via URIs of the form
`bond://<name>/<path>`, independent of the current working directory.

- `PersonaConfig` gains a `managed_directories` list; each entry has a `name`,
  a real filesystem `path`, and a `read_only` flag (default `False`).
- The instantiated `Persona` provides `resolve_path(path)`: URIs with the
  `bond://` prefix are mapped onto the matching managed directory; anything
  else is returned as-is.
- All path-taking tools in `tools/file_system/*` and `tools/pdf_tools.py`
  resolve their path arguments through the persona, so `bond://...` works
  everywhere a path is accepted.
- Access control: a resolved path inside a managed directory is pre-authorized
  (no confirmation prompt, works even outside the cwd and when
  `context.cwd is None`). Write operations into a `read_only` directory are
  denied, and the existing `.bond` / `.git` write protection still applies
  inside managed directories.
- `DefaultSystemMessageBuilder` gains an `include_managed_directories` flag;
  when enabled **and** the persona defines managed directories, a
  `<managed-directories>` section describing them is added to the system
  message. The section is omitted when there are none.

## Open questions / decisions

- **Access semantics** — decided with the user: managed directories are
  pre-authorized for read *and* write (no confirmation, even in
  non-interactive mode / outside cwd). `.bond`/`.git` write protection
  persists inside them.
- **Escape prevention vs. symlinks** — decided with the user: containment is
  checked **lexically** (`os.path.normpath`, no `resolve()`), so
  `bond://sandbox/../x` is rejected, but symlinked roots/targets work
  (e.g. the managed root or a parent being a symlink to another drive).
- **Grant based on resolved path, not URI syntax** — a literal absolute path
  that lexically lies inside a managed root is also treated as managed.
  Consequence: a path through the *resolved* (symlink-dereferenced) location
  of a managed dir is not auto-granted; the `bond://` URI is the reliable
  spelling. This is the safer direction.
- **Per-directory read-only** — decided with the user: `read_only: bool` on
  each `ManagedDirectory`.
- **System message** — opt-in flag `include_managed_directories` (default
  `False`, following the existing `include_*` convention), enabled in the
  Mistral and Ollama **generation** builders; rendered only when the persona
  actually defines managed directories.
- **Tool scope** — decided with the user: everything in
  `tools/file_system/*` that takes a path plus `pdf_tools.py`.
  `get_cwd` takes no path (unchanged). `working_set` tools store raw path
  strings for later rendering and are out of scope. `shell`/`local` tools are
  out of scope.
- **`cwd=None`** — happens only in the summarization task-list loop
  (`tool_loop_runner.py`). Plain paths stay disabled there; `bond://` URIs
  still resolve (that is the point of the feature).

## Design decisions

1. **`ManagedDirectory` model in `src/bond/persona.py`** — pydantic
   `BaseModel` with `name: str`, `path: str`, `read_only: bool = False`.
   Validators: `name` non-empty, no `/`, not `.`/`..`; `path` non-empty.
   `PersonaConfig.managed_directories: list[ManagedDirectory]` with a
   validator rejecting duplicate names. Config validation uses
   `extra="forbid"`, so the field must be declared explicitly (it is).
2. **`Persona` dataclass** gains `managed_directories: list[ManagedDirectory]
   = field(default_factory=list)` as the last field (all existing
   constructions use keyword args, so this is backward compatible);
   `PersonaConfig.instantiate()` passes `self.managed_directories` through.
3. **`Persona.resolve_path(path: str | Path) -> Path`** —
   - non-`bond://` input: returned as-is (`Path(raw)`), per spec;
   - `bond://<name>/<sub>`: look up `name`; unknown name → `ValueError`;
     root = `normpath(expanduser(path).absolute())`; target =
     `normpath(root / sub)`; if `not target.is_relative_to(root)` →
     `ValueError` (lexical escape like `..` rejected); otherwise return
     target (never `resolve()`d — symlinks keep working).
   Constant `MANAGED_DIR_URI_PREFIX = "bond://"` in `persona.py`. Parsing:
   strip the prefix, then split the rest on the first `/` into
   `<name>/<sub>` (a bare `bond://<name>` addresses the root itself).
4. **`Persona.managed_directory_for(path) -> ManagedDirectory | None`** —
   returns the managed directory whose normalized root lexically contains
   the given path (used by access checks).
5. **`ToolCallContext.resolve_path(raw_path) -> Path | None`** in
   `tools/tool.py` (moved there because non-file-system tools will use it
   too) — if a persona is present, call `persona.resolve_path(raw_path)`
   (catch `ValueError` at call sites); if the result is absolute, use it;
   else join with `context.cwd` (via existing `bond.util.resolve_path`).
   Returns `None` when the path is relative and `cwd is None` (filesystem
   disabled, current behavior).
6. **Access checks in `tools/file_system/util.py`**:
   - `check_access`: if `context.persona.managed_directory_for(path)`
     matches → `(True, "")` before the cwd logic.
   - `check_write_access`: keep `check_access` first, then the existing
     `.bond`/`.git` denial (so it persists inside managed dirs), then deny
     writes when the matched managed directory is `read_only`.
7. **Tool rewiring** — in `read_file`, `list_directory`, `create_file`,
   `remove_file`, `apply_patch` (per patch block), `search_file`, `grep`, and
   `pdf_tools._resolve_pdf_path`, replace the
   `if context.cwd is None: ...` + `resolve_path(context.cwd, ...)` pattern
   with `resolve_tool_path` + `ValueError` → error string + `None` →
   "filesystem disabled" error. In `apply_patch`, the git-based
   skip-confirmation check must tolerate `cwd=None`
   (`skip_confirmation = context.cwd is not None and ...`).
8. **System message** — `DefaultSystemMessageBuilder.__init__` gains
   `include_managed_directories: bool = False`. The persona-config
   resolution currently inline in `_render_skills_sections` is extracted
   into `_get_persona_config(conversation)` and reused. New
   `_render_managed_directories_section(...)` emits, only when the flag is
   on and the list is non-empty:

   ```
   <managed-directories>
   <reliability>trusted</reliability>
   <source>user configuration</source>
   <content>
   You have access to the following managed directories. Use them via
   `bond://<name>/<path>` in file tools (read_file, list_directory,
   create_file, apply_patch, remove_file, search_file, grep, pdf tools):
   - sandbox -> /abs/path (read-write)
   - archive -> /abs/path (read-only)
   </content>
   </managed-directories>
   ```

   Enabled via `include_managed_directories=True` in the generation builders
   of `providers/mistral/mistral.py` and `providers/ollama/ollama.py`.
9. **Alternatives considered** — resolving symlinks for containment
   (rejected: breaks symlinked roots the user explicitly wants);
   returning `Result` from `resolve_path` (rejected: `ValueError` is simpler
   and tools already return error strings); URI-only granting (rejected:
   resolved-path granting is harder to bypass accidentally).

## Task list

- [x] `persona.py`: add `MANAGED_DIR_URI_PREFIX`, `ManagedDirectory` model
      (with validators), `managed_directories` on `PersonaConfig` (+ duplicate
      name validator), `managed_directories` field on `Persona`,
      `Persona.resolve_path()`, `Persona.managed_directory_for()`, wire
      through `instantiate()`
- [x] `tools/tool.py`: `ToolCallContext.resolve_path()` (persona URI resolution
      + cwd fallback, `None` when cwd is `None`); `tools/file_system/util.py`:
      update `check_access()` (managed grant) and `check_write_access()`
      (`.bond`/`.git` still denied, read-only managed dirs denied)
- [x] Rewire `read_file`, `list_directory`, `create_file`, `remove_file`,
      `apply_patch`, `search_file`, `grep` to `context.resolve_path()`
      (incl. `cwd=None` tolerance in `apply_patch`'s skip-confirmation)
- [x] Rewire `pdf_tools._resolve_pdf_path()` to `context.resolve_path()`
- [ ] `default_system_message_builder.py`: `include_managed_directories`
      flag, `_get_persona_config()` refactor,
      `_render_managed_directories_section()` (omitted when empty)
- [ ] Enable `include_managed_directories=True` in the generation builders of
      `mistral.py` and `ollama.py`
- [ ] Tests: new `test/bond/test_persona_managed_directories.py`
      (resolve_path mapping/passthrough/unknown-name/escape/symlink root,
      read_only parsing, config validation, `managed_directory_for`);
      new `test/bond/tools/test_managed_dir_tools.py` (read via `bond://` with
      `cwd=None`, write denied in read-only dir, `.bond` inside managed dir
      still write-protected, escape and unknown-name error strings, grep,
      apply_patch block); extend
      `test_default_system_message_builder.py` (flag default off, section
      present with dirs + flag on, omitted when no dirs, omitted when flag
      off, read-only marker)
- [ ] Run full suite: `.bond/scripts/run-tests.sh`
- [ ] Docs: bullet in `README.md` personas section + short
      `docs/personas/managed-directories.md` (config example, URI syntax,
      read-only semantics, symlink/escape behavior)