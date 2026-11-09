# Feature plan: remove_file tool + .git write protection

## Overview

Two related changes to the file tools:

1. **New `remove_file` tool** in the `file` toolset: deletes a single file.
1. **Extend write protection to `.git` directories**: currently only `.bond` is
   protected in `check_write_access`, so `create_file` can write into `.git`.
   `apply_patch` already denies `.git` via its own `path_is_in_git` check.

## Open questions / decisions

- **remove_file semantics**: deletes **files only** — directories are refused
  (`error: path is a directory...`), no recursive delete. A symlink is removed
  as a link (`Path.unlink`), never its target. Decision: keep it safe and simple.
- **Confirmation**: mirror `apply_patch` — no prompt when `cwd/.git` exists
  (deletion of tracked files is recoverable via git), otherwise ask
  `ask_confirmation` in interactive mode; non-interactive without a
  confirmation prompt declines (same as `apply_patch`).
- **What gets protected**: any path with a `.git` component (same detection as
  the existing `path_is_in_git`), in addition to `.bond`. **Reads stay allowed**
  in both (consistent with the `.bond` policy: read-only, not invisible).
- **Where the check lives**: extend `check_write_access` in
  `src/bond/tools/file_system/util.py` with the `.git` denial, and make
  **`apply_patch` use `check_write_access` per block too**, dropping its own
  `path_is_in_git`/`path_is_in_bond` checks. The block-scoped prefix stays
  (`Block N: failed, <reason>`); the reason becomes the shared message
  (`Permission denied: '.git'/'.bond' directories are read-only for tools.`).
  Side effect (intended hardening): `check_write_access` also runs
  `check_access`, so patching a file outside the cwd now asks for confirmation
  in interactive mode instead of silently proceeding.
- **Denial messages**: `check_write_access` returns
  `Permission denied: '.git' directories are read-only for tools.` (mirrors
  the `.bond` message).

## Design decisions

- New file `src/bond/tools/file_system/remove_file.py`, registered in
  `file_system/__init__.py` (`__all__`) and in the `"file"` toolset in
  `src/bond/runtime.py`.
- `remove_file` flow: `cwd is None` → error; `resolve_path`; `check_write_access`
  (covers cwd restriction, `.git`, `.bond`); not exists → error; is dir → error;
  confirmation (git-skip rule); `path.unlink()` → `Removed file {path}`.
- No changes to read tools (`read_file`, `search_file`, `grep`, `list_directory`):
  they may still read `.git`/`.bond`.

## Task list

- [x] `util.py`: `check_write_access` also denies `path_is_in_git(path)` with the `.git` read-only message; docstring updated.
- [x] New `src/bond/tools/file_system/remove_file.py` with the tool + description.
- [x] Registered `remove_file` in `file_system/__init__.py` and `runtime.py` (`"file"` toolset).
- [x] `apply_patch.py`: per-block `path_is_in_git`/`path_is_in_bond` checks replaced by `check_write_access(context, path)` (keeps `Block N: failed, ...` prefix, uses the shared denial message); unused imports dropped; description mentions `.git`. Side effect (intended): patching outside the cwd now goes through `check_access` and asks in interactive mode.
- [x] `create_file.py` description mentions `.git` alongside `.bond`.
- [x] Tests: new `test/bond/tools/test_remove_file.py` (8 tests: remove ok, missing, directory refused, symlink link-not-target, git-repo skips confirmation, declined cancels, `.git`/`.bond` denied, outside-cwd non-interactive denied). `test_bond_write_protection.py` extended: `check_write_access` denies `.git`, `create_file` into `.git` denied, `apply_patch` into `.git` denied, existing `.bond` apply_patch assertion updated to the shared message.
- [x] Run full test suite (user-run per workflow, e.g. `.bond/scripts/run-tests.sh`); no regressions.
- [x] Docs: `docs/local-bond-dir.md` write-protection section now covers `.git` + `remove_file`.

## Progress / changes

- `src/bond/tools/file_system/util.py`: `check_write_access` denies `.bond` and `.git`.
- `src/bond/tools/file_system/remove_file.py`: new tool (files only, symlink-safe, git-skip confirmation, protected dirs denied).
- `src/bond/tools/file_system/apply_patch.py`: unified on `check_write_access` per block; old ad-hoc checks removed.
- `src/bond/tools/file_system/create_file.py`, `__init__.py`, `src/bond/runtime.py`: descriptions/registration.
- Tests + `docs/local-bond-dir.md` as above. No stale references to the old "inside .git folder" message remain outside the plan files.
