"""Discovery of the project-local ``.bond`` directory.

A ``.bond`` directory in the current working directory (or any parent of it)
extends the runtime with project-local skills, scripts and conversations::

    .bond/
      skills/<name>/SKILL.md    # local skills, same format as global ones
      scripts/                  # scripts runnable via the `local` toolset
      conversations/            # local conversation store (lsave / lload)

Only the *closest* ``.bond`` directory is used — if several parents up the
tree have one, the nearest one wins and the others are ignored (no merging).
"""

from pathlib import Path

LOCAL_DIR_NAME = ".bond"


def find_local_bond_dir(start: Path | None = None) -> Path | None:
    """Return the closest ancestor of *start* that contains a ``.bond``
    directory, or ``None`` if there is none.

    Args:
        start: Directory to start from (default: the current working
            directory). If *start* is a file, its parent is used.

    Returns:
        The absolute path of the discovered ``.bond`` directory (i.e.
        ``<ancestor>/.bond``), or ``None``.
    """
    current = (start or Path.cwd()).expanduser().absolute()
    if current.is_file():
        current = current.parent
    while True:
        candidate = current / LOCAL_DIR_NAME
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            pass
        if current.parent == current:
            return None
        current = current.parent
