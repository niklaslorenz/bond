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

import logging
import re

from pydantic import BaseModel, Field

from bond.conversation.conversation import Conversation
from bond.persona import Persona, PersonaConfig

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:[ \t]*(.*)$")


class Skill(BaseModel):
    """A parsed skill: metadata plus instructions."""

    name: str
    description: str = Field(default="")
    instructions: str = Field(default="")


def parse_skill_md(text: str, fallback_name: str) -> Skill:
    """Parse the content of a SKILL.md file into a :class:`Skill`.

    Args:
        text: Raw file content.
        fallback_name: Name to use when the frontmatter does not define one
            (typically the skill's directory name).

    Returns:
        The parsed Skill. The frontmatter ``name`` wins over ``fallback_name``;
        a missing description defaults to an empty string (with a warning).
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
                f"Skill '{fallback_name}' has no description in its SKILL.md frontmatter"
            )

    return Skill(
        name=name,
        description=description,
        instructions=instructions.strip("\r\n"),
    )


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
