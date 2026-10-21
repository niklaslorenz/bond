import logging

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="clear_tasks",
    description="Clear all tasks from the task list. Use this when starting fresh or when all tasks are no longer relevant. Changes become visible after summarization.",
    parameters={},
    required=[],
)
def clear_tasks(
    context: ToolCallContext,
) -> str:
    """Clear all tasks from the task list."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    if conversation.task_list is None or len(conversation.task_list) == 0:
        return "Task list is already empty."

    count = len(conversation.task_list)
    conversation.task_list.content = []

    logger.debug(f"Cleared {count} tasks from task list")

    return f"Cleared all {count} task(s) from the task list.\n\nNote: Changes will be visible in the task list after the next summarization."
