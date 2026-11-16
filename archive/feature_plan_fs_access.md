# Feature plan: unified file-system access (`fs_access`)

## Overview

Implements the README's "Refinements before release → Unified File permissions"
item: instead of every tool hand-rolling `context.resolve_path()` +
`check_access` / `check_write_access` (currently in
`src/bond/tools/file_system/util.py`), all path-taking tools go through one
module — `src/bond/fs_access.py` — via a single entry point on the tool
context:

```python
grant = context.request_fs_access(raw_path, AccessMode.READ, recursive=False)
# grant: Result[AuthorizedPath, str]
```

`AuthorizedPath` wraps a resolved `Path` together with the granted
read/write mode and a `recursive` flag. Its methods check the grant and
return `Result[...]` with a user-facing reason on failure, so a tool never
prompts twice for the same path and never touches the filesystem outside the
policy.

## Open questions / decisions

Decided with the user:

- **No grant cache for now.** Each `request_fs_access` call re-evaluates the
  policy from scratch. However, `ToolCallContext.cwd` and `.persona` become
  properties whose setters only fire an invalidation hook
  (`_on_fs_access_policy_change()`) when the value *actually changed* — so a
  session-long grant cache can be added later by just populating/invalidating
  in that hook. (The context object is session-long in the TUI:
  `tui/main.py:60` creates it once; `behaviours/async_loop.py:311-313`
  mutates `.persona`/`.cwd` per turn.)
- **Recursive denial semantics:** if the user denies a `recursive=True`
  request, the whole request fails (`Failure`). It is never silently
  downgraded to a non-recursive grant. A tool may re-request non-recursively
  itself if it wants.
- **Eager prompting:** the confirmation prompt happens inside
  `request_fs_access`, matching current behavior.
- **Hard denials never prompt:** writes into `.bond` / `.git`, writes into
  `read_only` managed directories, and relative paths with `cwd=None` return
  `Failure` immediately, even in interactive mode.
- **`apply_patch` / `remove_file`:** they use `request_fs_access` for path
  authorization. `request_fs_access` takes an optional `purpose: str` that is
  relayed to the user inside the permission prompt, so `apply_patch` can pass
  the patch block (or a summary) as the reason for the access request when it
  needs to touch files outside the cwd. The tools' own "apply changes?" /
  "remove file?" confirmations remain as separate, orthogonal prompts
  (git-based skip logic unchanged).
- **`local_tools` bypasses the system** (`.bond/scripts/` is an explicit
  allowlist — a wildcard by design). `shell_tools` keeps its own per-call
  confirmation. `working_set` tools store raw path strings and stay out of
  scope for this rework.

Still open (non-blocking, defaults chosen):

- Module shape: single module `src/bond/fs_access.py` now; can be promoted to
  a package later if it grows.
- Error strings keep their current wording (`"Permission denied ..."`,
  `"Error: ..."`) so existing tests keep passing unchanged.

## Design decisions

1. **`src/bond/fs_access.py`** — the single place that knows the policy.
   - `AccessMode(Enum)`: `READ`, `WRITE`. A `WRITE` grant also permits reads
     on the same path (today's `check_write_access` implies `check_access`;
     `apply_patch` reads and writes the same file under one write check).
   - `path_is_in_bond(path)` / `path_is_in_git(path)` move here from
     `tools/file_system/util.py` (that module keeps only the fuzzy-matching
     helpers `normalize`, `fuzzy_find_aider_patch_blocks`, `fuzzy_contains`).
   - `classify(context, path, mode) -> Grant` where `Grant` is one of:
     - `PreAuthorized` — path inside a persona-managed directory
       (`Persona.managed_directory_for`, `persona.py:113`), or inside
       `context.cwd`;
     - `Denied(reason)` — `.bond`/`.git` on WRITE, `read_only` managed dir
       on WRITE, `cwd is None` (filesystem disabled);
     - `NeedsConfirmation` — absolute path outside cwd; only interactive
       sessions can be granted (non-interactive → `Denied`).
   - `AuthorizedPath` — dataclass with `path: Path`, `mode: AccessMode`,
     `recursive: bool`, `_is_root: bool` (the requested path vs. a derived
     child). Methods:
     - metadata (plain bools / stat, never gated by content rules — needed
       for listing): `exists()`, `is_file()`, `is_dir(follow_symlinks=True)`,
       `is_symlink()`, `stat() -> Result[os.stat_result, str]`;
     - content/structure, gated by `mode` and, for derived children,
       `recursive`: `read_text() -> Result[str, str]`,
       `read_bytes() -> Result[bytes, str]`,
       `iterdir() -> Result[list[AuthorizedPath], str]` (children inherit
       mode + recursive flag, `_is_root=False`),
       `child(rel) -> Result[AuthorizedPath, str]`,
       `write_text(content) -> Result[None, str]` (creates parent dirs,
       like `create_file` does today), `unlink() -> Result[None, str]`.
     - gating rule: a content/descend method on the root is allowed per
       `mode`; on a derived child it additionally requires `recursive=True`.
       This reproduces today's semantics exactly: `list_directory` prompts
       once for the dir and lists one level; `tree`/recursive `grep` need
       `recursive=True`; reading a child of a listed outside-cwd dir requires
       a fresh `request_fs_access` (which prompts again), because there is
       no cache.
     - `.path` property exposes the raw `Path` for subprocesses
       (`grep`/`rg`) and anything else that cannot go through Python methods.
2. **`ToolCallContext` changes** (`src/bond/tools/tool.py`):
   - `cwd: Path | None` and `persona: Persona | None` become properties
     backed by private fields; setters compare `old != new` and call
     `_on_fs_access_policy_change()` only on change. The hook is a no-op
     today (extension point for the future grant cache). `conversation`
     stays a plain field.
   - New method `request_fs_access(raw_path, mode=AccessMode.READ,
     *, recursive=False, purpose: str | None = None)
     -> Result[AuthorizedPath, str]`:
     - resolves via the existing `self.resolve_path(raw_path)` (bond:// URIs
       + cwd join, `tool.py:116`); `ValueError` → `Failure(f"Error: {e}")`,
       `None` (cwd disabled, relative path) →
       `Failure("Error: Tool access to the filesystem is currently disabled.")`;
     - runs `classify()`; `Denied` → `Failure(reason)`;
       `PreAuthorized` → `Success(AuthorizedPath(..., _is_root=True))`;
       `NeedsConfirmation` → if not interactive → `Failure(...)` (current
       wording), else `ask_confirmation(prompt)` with the current prompt
       text, extended with "including everything inside it" when
       `recursive=True` and the path is a dir, and with the `purpose` text
       when given; granted → `Success(...)`,
       denied → `Failure("Permission denied, the user has declined your
       request.")`.
   - `resolve_path()` stays public (tests use it).
3. **Tool rewiring** — each tool replaces the
   `resolve_path` / `None`-check / `check_access|check_write_access`
   boilerplate with `request_fs_access` + wrapper calls:
   - `read_file.py`, `search.py`: READ → `read_text()`; keep
     "error: not a file" behavior via `is_file()`.
   - `list_directory.py`: READ → `is_dir()` + `iterdir()`.
   - `tree.py`: READ `recursive=True` → recursive `iterdir()` walk
     (children are `AuthorizedPath`s; symlink handling via
     `is_symlink()` / `is_dir(follow_symlinks=False)`).
   - `grep.py`: READ `recursive=recursive` on the search path; for
     non-recursive dir searches, `iterdir()` + per-file subprocess on
     `child.path` (the per-file `check_access` at `grep.py:165` disappears).
     Subprocess still runs with `cwd=context.cwd` as today.
   - `create_file.py`: WRITE → `exists()` check ("error: file already
     exists") + `write_text()` (which mkdirs parents).
   - `apply_patch.py`: per patch block, WRITE with `purpose=` describing the
     block → `exists()` + `read_text()` + `write_text()`; the block-level
     `check_write_access` disappears; the patch confirmation dialog
     (git-based skip + `ask_confirmation`) stays unchanged.
   - `remove_file.py`: WRITE → `exists()`/`is_symlink()`/`is_dir()` +
     `unlink()`; its own removal confirmation stays unchanged.
   - `pdf_tools.py`: `_resolve_pdf_path` becomes `request_fs_access(READ)`;
     `read_bytes()` → `pypdf.PdfReader(io.BytesIO(data))`; `stat()` for the
     file size in `pdf_info`.
   - `get_cwd.py`: no path, unchanged.
4. **Deletion:** `check_access`, `check_write_access` removed from
   `tools/file_system/util.py`; all imports updated. `file_system/__init__.py`
   exports unchanged (tool functions keep their names).
5. **Alternatives considered:**
   - keeping `check_access`/`check_write_access` and wrapping them — rejected:
     keeps the scattered policy and the per-tool boilerplate the README wants
     gone;
   - lazy prompting (prompt on first wrapper method call) — rejected for now:
     changes when prompts appear vs. today; eager matches current UX;
   - `Result` vs exceptions for wrapper methods — `Result` chosen, consistent
     with the codebase (`returns.result` used in `tool_call_loop.py`,
     `persona.py`).

## Task list

- [x] `src/bond/fs_access.py`: `AccessMode`, `AuthorizedPath`, `classify()`,
      moved `path_is_in_bond` / `path_is_in_git`, prompt + error strings
      (preserving current wording)
- [x] `src/bond/tools/tool.py`: `cwd`/`persona` as change-detecting
      properties + `_on_fs_access_policy_change()` no-op hook;
      `request_fs_access()` on `ToolCallContext`
- [x] Rewire read tools: `read_file`, `list_directory`, `tree`, `search_file`,
      `grep`
- [x] Rewire write tools: `create_file`, `apply_patch`, `remove_file`
      (own confirmations untouched)
- [x] Rewire `pdf_tools.py` (`read_bytes` + `BytesIO`, `stat` for size)
- [x] Remove `check_access` / `check_write_access` from
      `tools/file_system/util.py`; update all imports
- [x] New tests `test/bond/tools/test_fs_access.py`: classification matrix
      (inside cwd, outside cwd interactive/non-interactive, managed rw/ro,
      `.bond`/`.git` read vs write, `cwd=None`, `bond://` unknown name +
      escape errors), recursive grant covers subtree, non-recursive children
      are metadata-only, denied recursive request is not downgraded, WRITE
      grant allows reads, wrapper method failures ("not a file", "does not
      exist", OS errors)
- [x] Update `test_bond_write_protection.py` to the new API (local
      `check_write_access` helper over `request_fs_access`);
      `test_managed_dir_tools.py` needed no changes (tool-level assertions
      on message wording all still pass)
- [x] Run full suite: `.bond/scripts/run-tests.sh` — 996 passed
- [x] README: "Unified File permissions" moved out of the release-refinement
      TODO into a feature entry documenting the new module
