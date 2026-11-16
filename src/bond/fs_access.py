"""Unified file-system access policy for tools.

This module is the single place that decides whether a tool may read or write
a path. Tools never check permissions on their own — they call
``ToolCallContext.request_fs_access`` (which delegates here) and then operate
through the returned :class:`AuthorizedPath` wrapper, whose methods enforce
the grant and return ``Result`` with a reason on failure.

Policy (re-evaluated on every request — no caching yet):

- Paths inside a persona-managed directory (``bond://<name>/...``) are
  pre-authorized for reads, even when ``cwd`` is disabled. Writes are
  additionally denied when the managed directory is ``read_only``.
- Paths inside the current working directory are pre-authorized.
- Absolute paths outside the cwd require an interactive confirmation; in
  non-interactive mode they are denied.
- ``.bond`` and ``.git`` directories are read-only for tools everywhere
  (including inside managed directories) — writes are hard-denied without
  prompting.
- ``cwd=None`` disables plain filesystem access (``bond://`` URIs still
  resolve, since they are absolute after persona resolution).

A grant covers exactly the requested path; with ``recursive=True`` it covers
the whole subtree. Children derived via ``iterdir()`` / ``child()`` inherit
the mode and the recursive flag, but content operations on them require a
recursive grant (``is_root=False``). A denied recursive request is never
silently downgraded to a non-recursive grant.
"""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from returns.result import Failure, Result, Success

if TYPE_CHECKING:
    from bond.tools.tool import ToolCallContext


class AccessMode(Enum):
    """What kind of access is requested for a path."""

    READ = "read"
    WRITE = "write"


def path_is_in_git(path: Path) -> bool:
    """Check if a path is inside a .git folder."""
    for x in path.parts:
        if x == ".git":
            return True
    return False


def path_is_in_bond(path: Path) -> bool:
    """Check if a path is inside any .bond folder (any path component)."""
    for x in path.parts:
        if x == ".bond":
            return True
    return False


@dataclass
class PreAuthorized:
    """Access is granted without asking (managed directory or inside cwd)."""


@dataclass
class Denied:
    """Access is hard-denied; ``reason`` is the user-facing message."""

    reason: str


@dataclass
class NeedsConfirmation:
    """Access is outside the cwd and can only be granted interactively."""


Grant = PreAuthorized | Denied | NeedsConfirmation
"""Outcome of :func:`classify` — no prompting happens there."""


def classify(context: "ToolCallContext", path: Path, mode: AccessMode) -> Grant:
    """Classify access to ``path`` under ``mode`` without prompting."""
    persona = context.persona
    if persona is not None and persona.managed_directory_for(path) is not None:
        base: Grant = PreAuthorized()
    else:
        work_dir = context.cwd
        if work_dir is None:
            return Denied(
                "Permission denied, tool access to the filesystem is currently"
                " disabled."
            )
        if path.is_relative_to(work_dir):
            base = PreAuthorized()
        elif not context.is_interactive:
            return Denied(
                "Permission denied, this tool is not run in interactive mode."
                f" Cannot access files outside of '{work_dir}'"
            )
        else:
            base = NeedsConfirmation()
    if mode is AccessMode.WRITE:
        if path_is_in_bond(path):
            return Denied(
                "Permission denied: `.bond` directories are read-only for tools."
            )
        if path_is_in_git(path):
            return Denied(
                "Permission denied: `.git` directories are read-only for tools."
            )
        if persona is not None:
            managed_dir = persona.managed_directory_for(path)
            if managed_dir is not None and managed_dir.read_only:
                return Denied(
                    f"Permission denied: managed directory '{managed_dir.name}'"
                    " is read-only."
                )
    return base


def build_confirmation_prompt(path: Path, recursive: bool, purpose: str | None) -> str:
    """Build the prompt shown when access outside the cwd needs confirmation."""
    prompt = (
        f"Bond wants to access the contents of {path}, which lies outside of"
        " the current working directory."
    )
    if recursive and path.is_dir():
        prompt += (
            " The request is recursive: it covers all files and directories"
            " inside it as well."
        )
    if purpose is not None:
        prompt += f"\n{purpose}"
    prompt += "\nDo you want to grant access?"
    return prompt


@dataclass
class AuthorizedPath:
    """A resolved path together with the access grant that covers it.

    Metadata methods (``exists``, ``is_file``, ``is_dir``, ``is_symlink``,
    ``stat``, ``readlink``) are always available — they are needed to list
    directories. Content and structure methods (``read_text``, ``read_bytes``,
    ``write_text``, ``unlink``, ``iterdir``, ``child``) check the grant: they
    are allowed on the granted path itself (``is_root=True``), and on derived
    children only when the grant is ``recursive``. Read operations are allowed
    under both READ and WRITE grants (a write grant implies reading the same
    path); write operations only under a WRITE grant.

    Use the ``path`` attribute for anything that cannot go through these
    methods (e.g. passing a path to a subprocess).
    """

    path: Path
    mode: AccessMode
    recursive: bool = False
    is_root: bool = True

    def _gate(self, needed: AccessMode) -> str | None:
        """Return an error message if the grant does not cover this operation."""
        if not (self.is_root or self.recursive):
            return (
                f"Permission denied: '{self.path}' is not covered by the access"
                " grant (the grant is not recursive)."
            )
        if needed is AccessMode.WRITE and self.mode is not AccessMode.WRITE:
            return f"Permission denied: no write access granted for '{self.path}'."
        return None

    # --- metadata (ungated) ---

    def exists(self) -> bool:
        return self.path.exists()

    def is_file(self) -> bool:
        return self.path.is_file()

    def is_dir(self, follow_symlinks: bool = True) -> bool:
        if follow_symlinks:
            return self.path.is_dir()
        return not self.path.is_symlink() and self.path.is_dir()

    def is_symlink(self) -> bool:
        return self.path.is_symlink()

    def stat(self) -> Result[os.stat_result, str]:
        try:
            return Success(self.path.stat())
        except OSError as e:
            return Failure(f"Error: cannot stat '{self.path}': {e}")

    def readlink(self) -> Result[str, str]:
        try:
            return Success(os.readlink(self.path))
        except OSError as e:
            return Failure(f"Error: cannot read symlink '{self.path}': {e}")

    # --- content / structure (gated) ---

    def read_text(self) -> Result[str, str]:
        if not self.path.is_file():
            return Failure("error: not a file")
        if (err := self._gate(AccessMode.READ)) is not None:
            return Failure(err)
        try:
            return Success(self.path.read_text(encoding="utf-8"))
        except OSError as e:
            return Failure(f"Error reading file '{self.path}': {e}")

    def read_bytes(self) -> Result[bytes, str]:
        if not self.path.is_file():
            return Failure("error: not a file")
        if (err := self._gate(AccessMode.READ)) is not None:
            return Failure(err)
        try:
            return Success(self.path.read_bytes())
        except OSError as e:
            return Failure(f"Error reading file '{self.path}': {e}")

    def write_text(self, content: str) -> Result[None, str]:
        """Write ``content`` to the file, creating parent directories."""
        if (err := self._gate(AccessMode.WRITE)) is not None:
            return Failure(err)
        try:
            if not self.path.parent.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(content, encoding="utf-8")
            return Success(None)
        except OSError as e:
            return Failure(f"Error writing file '{self.path}': {e}")

    def unlink(self) -> Result[None, str]:
        if (err := self._gate(AccessMode.WRITE)) is not None:
            return Failure(err)
        try:
            self.path.unlink()
            return Success(None)
        except OSError as e:
            return Failure(f"Error removing file: {e}")

    def iterdir(self) -> Result[list["AuthorizedPath"], str]:
        """List the entries of a directory as derived (non-root) children."""
        if (err := self._gate(AccessMode.READ)) is not None:
            return Failure(err)
        if not self.path.is_dir():
            return Failure("Error: not a directory")
        try:
            children = list(self.path.iterdir())
        except OSError as e:
            return Failure(f"Error: cannot read directory '{self.path}': {e}")
        return Success(
            [
                AuthorizedPath(
                    path=c, mode=self.mode, recursive=self.recursive, is_root=False
                )
                for c in children
            ]
        )

    def child(self, rel: str | Path) -> Result["AuthorizedPath", str]:
        """Derive a child path; refuses lexical escapes (``..``)."""
        if not self.path.is_dir():
            return Failure(f"Error: not a directory")
        target = Path(os.path.normpath(self.path / rel))
        if not target.is_relative_to(self.path):
            return Failure(f"Permission denied: '{rel}' escapes '{self.path}'.")
        return Success(
            AuthorizedPath(
                path=target, mode=self.mode, recursive=self.recursive, is_root=False
            )
        )


def request_fs_access(
    context: "ToolCallContext",
    raw_path: str | Path,
    mode: AccessMode = AccessMode.READ,
    *,
    recursive: bool = False,
    purpose: str | None = None,
) -> Result[AuthorizedPath, str]:
    """Resolve ``raw_path`` and authorize access to it under ``mode``.

    Returns ``Success(AuthorizedPath)`` when access is granted (pre-authorized
    or confirmed by the user) and ``Failure(reason)`` otherwise — including
    ``bond://`` resolution errors, a disabled filesystem (``cwd=None`` with a
    relative path), hard denials (``.bond``/``.git`` writes, ``read_only``
    managed directories) and declined confirmations.

    ``recursive=True`` asks for access to the whole subtree; if the user
    declines, the request fails as a whole (no silent non-recursive
    downgrade). ``purpose`` is relayed to the user inside the confirmation
    prompt so they can see *why* access is requested.
    """
    try:
        path = context.resolve_path(raw_path)
    except ValueError as e:
        return Failure(f"Error: {e}")
    if path is None:
        return Failure("Error: Tool access to the filesystem is currently disabled.")
    grant = classify(context, path, mode)
    if isinstance(grant, Denied):
        return Failure(grant.reason)
    if isinstance(grant, PreAuthorized):
        return Success(
            AuthorizedPath(path=path, mode=mode, recursive=recursive, is_root=True)
        )
    # NeedsConfirmation — classify only returns this for interactive sessions
    prompt = build_confirmation_prompt(path, recursive, purpose)
    if not context.ask_confirmation(prompt):
        return Failure("Permission denied, the user has declined your request.")
    return Success(
        AuthorizedPath(path=path, mode=mode, recursive=recursive, is_root=True)
    )
