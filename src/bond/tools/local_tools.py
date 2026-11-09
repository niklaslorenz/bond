"""Tools for the project-local ``.bond`` directory (the ``local`` toolset).

The ``local`` toolset lets the agent discover and run the scripts a project
ships in ``.bond/scripts/``. Unlike the shell toolset this never gives the
agent arbitrary shell access: only regular files directly inside
``.bond/scripts/`` can be executed, always via ``subprocess`` with
``shell=False`` (no shell interpretation of arguments), and no per-call
confirmation is needed — the user-controlled ``.bond/scripts/`` directory is
the explicit allowlist of what the agent may run.
"""

import logging
import stat
import subprocess
import sys
from pathlib import Path

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)

_MAX_OUTPUT_LINES = 50
_DEFAULT_TIMEOUT_S = 60


def _get_runtime():
    # Function-local import: bond.runtime imports this module for the builtin
    # toolset, so a module-level import would be circular.
    from bond.runtime import BondRuntime

    return BondRuntime.get_instance()


def _script_description(path: Path) -> str:
    """One-line description from the first ``# ...`` comment (shebang skipped)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#!"):
                    continue
                if line.startswith("#"):
                    return line.lstrip("#").strip()
                return ""
    except OSError:
        return ""
    return ""


def _build_command(script: Path) -> list[str]:
    """Pick how to execute *script* without involving a shell."""
    mode = script.stat().st_mode
    if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        return [str(script)]
    suffix = script.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(script)]
    if suffix == ".sh":
        return ["sh", str(script)]
    # Fall back to direct execution (works for binaries and OS-handled files).
    return [str(script)]


@tool.tool(
    name="list_local_scripts",
    description="""
    List the scripts available in the project-local `.bond/scripts/` directory,
    with their one-line descriptions. Use this to discover which local scripts
    can be run with `run_local_script`.
    Returns an error if there is no `.bond` directory for the current project.
    """,
    parameters={},
    required=[],
)
def list_local_scripts(context: ToolCallContext) -> str:
    """List the scripts in ``.bond/scripts/`` (non-recursive)."""
    runtime = _get_runtime()
    scripts_path = runtime.get_local_scripts_path()
    if scripts_path is None:
        return (
            "Error: no local `.bond` directory found (searched from the current "
            "working directory upwards)."
        )
    if not scripts_path.is_dir():
        return f"No scripts directory at {scripts_path}."
    try:
        entries = sorted(p for p in scripts_path.iterdir() if p.is_file())
    except OSError as e:
        return f"Error: could not list {scripts_path}: {e}"
    if not entries:
        return f"No scripts in {scripts_path}."
    lines = [f"Local scripts in {scripts_path}:"]
    for entry in entries:
        desc = _script_description(entry)
        lines.append(f"  - {entry.name}" + (f" — {desc}" if desc else ""))
    return "\n".join(lines)


@tool.tool(
    name="run_local_script",
    description="""
    Run a script from the project-local `.bond/scripts/` directory.
    Only files directly inside `.bond/scripts/` can be executed — that
    directory is an explicit allowlist of project scripts, so the script runs
    without asking for confirmation. Use `list_local_scripts` to see what is
    available. Arguments are passed to the script as-is; no shell is involved.
    The script runs with the project root (the directory containing `.bond`)
    as its working directory.
    """,
    parameters={
        "script_name": tool.FunctionParameter(
            type="string",
            description=(
                "File name of the script inside `.bond/scripts/` "
                "(e.g. 'run-tests.sh'). Plain file name only, no path separators."
            ),
        ),
        "args": tool.FunctionParameter(
            type="array",
            description="Arguments to pass to the script",
        ),
        "timeout": tool.FunctionParameter(
            type="integer",
            description=f"Timeout in seconds (default {_DEFAULT_TIMEOUT_S})",
        ),
    },
    required=["script_name"],
)
def run_local_script(
    context: ToolCallContext,
    script_name: str,
    args: list[str] | None = None,
    timeout: int = _DEFAULT_TIMEOUT_S,
) -> str:
    """Run a script from ``.bond/scripts/`` with ``shell=False``."""
    runtime = _get_runtime()
    bond_dir = runtime.get_local_bond_dir()
    if bond_dir is None:
        return (
            "Error: no local `.bond` directory found (searched from the current "
            "working directory upwards), so there are no local scripts to run."
        )
    scripts_path = runtime.get_local_scripts_path()
    assert scripts_path is not None

    if (
        "/" in script_name
        or "\\" in script_name
        or ".." in Path(script_name).parts
    ):
        return (
            f"Error: invalid script name '{script_name}': must be a plain file "
            "name inside `.bond/scripts/`."
        )

    script = (scripts_path / script_name).resolve()
    if script.parent != scripts_path.resolve():
        # e.g. a symlink pointing outside of .bond/scripts/
        return (
            f"Error: '{script_name}' resolves outside of {scripts_path}; "
            "only files directly inside `.bond/scripts/` can be run."
        )
    if not script.is_file():
        return f"Error: no such script '{script_name}' in {scripts_path}."

    command = _build_command(script) + list(args or [])
    timeout = max(1, int(timeout))
    logger.info(f"Running local script: {command} (cwd={bond_dir.parent})")
    try:
        proc = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=bond_dir.parent,
        )
    except subprocess.TimeoutExpired:
        return f"Error: script '{script_name}' timed out after {timeout}s."
    except PermissionError:
        return (
            f"Error: script '{script_name}' is not executable and has no known "
            "interpreter (.py / .sh)."
        )
    except OSError as e:
        return f"Error: could not run script '{script_name}': {e}"

    out_lines = proc.stdout.splitlines()[-_MAX_OUTPUT_LINES:]
    err_lines = proc.stderr.splitlines()[-_MAX_OUTPUT_LINES:]
    result = [f"exit code: {proc.returncode}", "stdout:"] + out_lines
    if err_lines:
        result.append("stderr:")
        result += err_lines
    return "\n".join(result)
