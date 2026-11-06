import logging

from bond.skill import effective_available_skills
from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="load_skill",
    description=(
        "Load a skill into the current conversation. The skill must be listed in "
        "the available skills. Its instructions are added to the system prompt, "
        "where they stay visible until the skill is unloaded."
    ),
    parameters={
        "name": tool.FunctionParameter(
            type="string",
            description=(
                "The name of the skill to load (as listed in the available skills)"
            ),
        ),
    },
    required=["name"],
)
def load_skill(
    context: ToolCallContext,
    name: str,
) -> str:
    """Activate a skill in the current conversation.

    The skill content itself is intentionally NOT returned here: it is rendered
    into the system prompt by the system message builder (the single place where
    active skill content lives), so it must not be duplicated into the tool
    result / message history.
    """
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    available = effective_available_skills(conversation, context.persona)
    if name not in available:
        if available:
            available_str = ", ".join(available)
            return (
                f"Error: Skill '{name}' is not available for this conversation. "
                f"Available skills: {available_str}"
            )
        return (
            f"Error: Skill '{name}' is not available for this conversation. "
            "No skills are available."
        )

    # Function-local import: bond.runtime imports this module for the builtin
    # toolset, so a module-level import would be circular.
    from bond.runtime import BondRuntime

    try:
        skill = BondRuntime.get_instance().get_skill(name)
    except Exception as e:
        logger.error(f"Failed to load skill '{name}': {e}")
        return f"Error: Could not load skill '{name}': {e}"

    if name in conversation.active_skills:
        return (
            f"Skill '{name}' is already active. "
            "Its instructions are included in the system prompt."
        )

    conversation.active_skills.append(name)
    logger.debug(f"Activated skill '{name}' ({skill.description}) in conversation")
    return (
        f"Skill '{name}' activated. Its instructions are now included in the "
        "system prompt."
    )


@tool.tool(
    name="unload_skill",
    description=(
        "Unload a skill from the current conversation. The skill's instructions will "
        "no longer be included in the system prompt."
    ),
    parameters={
        "name": tool.FunctionParameter(
            type="string",
            description="The name of the active skill to unload",
        ),
    },
    required=["name"],
)
def unload_skill(
    context: ToolCallContext,
    name: str,
) -> str:
    """Remove a skill from the conversation's active skills."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    if name not in conversation.active_skills:
        if conversation.active_skills:
            active_str = ", ".join(conversation.active_skills)
            return (
                f"Error: Skill '{name}' is not active. "
                f"Active skills: {active_str}"
            )
        return f"Error: Skill '{name}' is not active. No skills are active."

    conversation.active_skills.remove(name)
    logger.debug(f"Deactivated skill '{name}' in conversation")

    if conversation.active_skills:
        remaining = ", ".join(conversation.active_skills)
        return f"Skill '{name}' unloaded. Active skills: {remaining}"
    return f"Skill '{name}' unloaded. No skills are active anymore."
