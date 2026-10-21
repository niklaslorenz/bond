import logging

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="clear_working_set",
    description="Clear all items from the working set. Use this when you want to start fresh with a clean working set. Changes become visible after summarization.",
    parameters={},
    required=[],
)
def clear_working_set(
    context: ToolCallContext,
) -> str:
    """Clear all items from the working set."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    if conversation.working_set is None or len(conversation.working_set) == 0:
        return "Working set is already empty."

    count = conversation.working_set.clear()

    logger.debug(f"Cleared {count} items from working set")

    return f"Cleared all {count} item(s) from the working set.\n\nNote: Changes will be visible in the working set after the next summarization."
