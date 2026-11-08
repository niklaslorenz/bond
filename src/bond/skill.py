"""Skill model and SKILL.md parsing.

A skill is a directory under ``~/.config/bond/skills/<name>/`` containing a
``SKILL.md`` file with an optional YAML-ish frontmatter block::

    ---
    name: pdf-tools
    description: Tools for extracting and analyzing PDFs.
    ---
    # Instructions
    Use these tools when the user mentions PDFs.

The frontmatter is parsed manually (no yaml dependency); only ``name`` and
``description`` keys are understood. Everything after the closing ``---`` is
the skill's instructions.
"""

import importlib.util
import logging
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, cast

from pydantic import BaseModel, Field, PrivateAttr
from returns.result import Result

from bond.conversation.conversation import Conversation
from bond.persona import Persona, PersonaConfig
from bond.tools.toolbox import PrefixedToolset, Toolset

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:[ \t]*(.*)$")


class Skill(BaseModel):
    """A parsed skill: metadata plus instructions."""

    name: str
    description: str = Field(default="")
    instructions: str = Field(default="")
    path: Path | None = None
    _toolsets: list[Toolset] | None = PrivateAttr(None)

    @property
    def toolsets(self) -> list[Toolset]:
        if self._toolsets is None:
            self._toolsets = (
                _load_skill_toolsets(self.path, self.name)
                if self.path is not None
                else []
            )
        return self._toolsets

    @classmethod
    def load_from(cls, skill_path: Path, fallback_name: str) -> "Result[Skill, str]":
        md_path = skill_path / "SKILL.md"
        if not md_path.exists():
            return Result.from_failure(f"SKILL.md file does not exist in {skill_path}")
        name, description, instructions = _parse_skill_md(
            md_path.read_text(encoding="utf-8"), fallback_name
        )
        return Result.from_value(
            Skill(
                name=name,
                description=description,
                instructions=instructions,
                path=skill_path,
            )
        )


def _parse_skill_md(text: str, fallback_name: str) -> tuple[str, str, str]:
    """Parse the content of a SKILL.md file into a :class:`Skill`.

    Args:
        text: Raw file content.
        fallback_name: Name to use when the frontmatter does not define one
            (typically the skill's directory name).

    Returns:
        name, description, instructions
    """
    name = fallback_name
    description = ""
    instructions = text

    match = _FRONTMATTER_RE.match(text)
    if match is not None:
        frontmatter = match.group(1)
        instructions = text[match.end() :]
        for line in frontmatter.splitlines():
            kv = _KEY_VALUE_RE.match(line.strip())
            if kv is None:
                continue
            key, value = kv.group(1).lower(), kv.group(2).strip().strip('"').strip("'")
            if key == "name" and value:
                name = value
            elif key == "description":
                description = value
        if not description:
            logger.warning(
                f"Skill '{name}' has no description in its SKILL.md frontmatter"
            )

    return name, description, instructions.strip("\r\n")


def render_skill_md(skill: Skill) -> str:
    """Render a :class:`Skill` back to SKILL.md format (frontmatter + instructions)."""
    lines = ["---", f"name: {skill.name}"]
    if skill.description:
        lines.append(f"description: {skill.description}")
    lines.append("---")
    return "\n".join(lines) + "\n" + skill.instructions


def effective_available_skills(
    conversation: Conversation, persona: Persona | PersonaConfig | None
) -> list[str]:
    """Resolve which skills a conversation may use.

    Single source of truth shared by the skill tools and the system message
    builder: an explicit ``conversation.available_skills`` list wins; otherwise
    the persona's ``available_skills`` are used (``None`` persona -> none).

    Accepts either an instantiated :class:`Persona` or a raw
    :class:`PersonaConfig`.
    """
    if conversation.available_skills is not None:
        return conversation.available_skills
    if persona is None:
        return []
    if isinstance(persona, Persona):
        return persona.config.available_skills
    return persona.available_skills


def prune_active_skills(conversation: Conversation, available: list[str]) -> list[str]:
    """Enforce the invariant ``active_skills ⊆ available`` on a conversation.

    Removes every entry of ``conversation.active_skills`` that is not in
    ``available`` (the effective available list) and returns the removed
    names, so callers can report them. Entries are removed in place.
    """
    removed = [name for name in conversation.active_skills if name not in available]
    if removed:
        conversation.active_skills = [
            name for name in conversation.active_skills if name in available
        ]
    return removed


_TOOL_FILE_RE = re.compile(r"\A(tool_.+|.*_tools?)\.py\Z")


@contextmanager
def _skill_tools_on_sys_path(tools_path: Path):
    """Temporarily add the skill's ``tools/`` dir to ``sys.path`` so tool
    files can import sibling modules."""
    sys.path.insert(0, str(tools_path))
    try:
        yield
    finally:
        sys.path.remove(str(tools_path))


def _discover_tool_files(tools_path: Path) -> list[Path]:
    """Return the skill's tool files: ``*.py`` directly in ``tools/`` whose
    stem starts with ``tool_`` or ends with ``_tool`` / ``_tools``."""
    if not tools_path.is_dir():
        return []
    try:
        return sorted(
            f for f in tools_path.glob("*.py") if _TOOL_FILE_RE.match(f.name)
        )
    except OSError:
        logger.exception(f"Could not scan skill tools directory {tools_path}")
        return []


def _import_tool_module(skill_name: str, file: Path):
    """Import a single tool file under a unique module name. Never raises."""
    module_name = f"bond_skilltool_{skill_name}_{file.stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, file)
        if spec is None or spec.loader is None:
            logger.error(f"Could not create import spec for {file}")
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except KeyboardInterrupt:
        raise
    except BaseException:
        # Tool files are third-party code: contain even SystemExit etc.
        logger.exception(f"Error while importing skill tool file {file}")
        sys.modules.pop(module_name, None)
        return None


def _export_toolsets_from_module(module, file: Path) -> list[Toolset]:
    """Read ``EXPORT_TOOLSETS`` from an imported module and normalize it to a
    list of Toolsets. Missing/invalid entries are logged and skipped."""
    exported = getattr(module, "EXPORT_TOOLSETS", None)
    if exported is None:
        logger.warning(f"{file.name} does not export EXPORT_TOOLSETS; skipping")
        return []
    if isinstance(exported, (str, bytes)):
        logger.warning(
            f"EXPORT_TOOLSETS in {file.name} is a string, expected an iterable "
            f"of Toolsets or a callable; skipping"
        )
        return []
    if callable(exported):
        try:
            exported = exported()
        except Exception:
            logger.exception(f"EXPORT_TOOLSETS() in {file} raised; skipping")
            return []
    toolsets: list[Toolset] = []
    for item in cast(Iterable, exported):
        if isinstance(item, Toolset):
            toolsets.append(item)
        else:
            logger.warning(
                f"EXPORT_TOOLSETS in {file} contains non-Toolset item "
                f"{item!r}; skipping"
            )
    return toolsets


def _load_skill_toolsets(skill_path: Path, skill_name: str) -> list[Toolset]:
    """Discover, import and namespace the toolsets a skill provides.

    Tool files live in ``<skill_path>/tools/`` and are imported lazily here.
    Each exported toolset is wrapped in a :class:`PrefixedToolset` so the
    toolset name and every tool name carry the ``sk:<skill_name>:`` prefix.
    Never raises — broken files are logged and skipped. Results are cached on
    the owning :class:`Skill` instance (``_toolsets``), which the runtime keeps
    alive, so tool files are imported at most once per loaded skill.
    """
    prefix = f"sk:{skill_name}:"
    tools_path = skill_path / "tools"
    toolsets: list[Toolset] = []
    for file in _discover_tool_files(tools_path):
        try:
            with _skill_tools_on_sys_path(tools_path):
                module = _import_tool_module(skill_name, file)
            if module is None:
                continue
            for toolset in _export_toolsets_from_module(module, file):
                toolsets.append(PrefixedToolset(toolset, prefix))
        except Exception:
            logger.exception(f"Error while loading skill tool file {file}; skipping")
    return toolsets
