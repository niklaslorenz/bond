import logging

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="clear_completed_tasks",
    description="Remove all completed tasks from the task list. Use this to clean up the task list after completing several tasks. Changes become visible after summarization.",
    parameters={},
    required=[],
)
def clear_completed_tasks(
    context: ToolCallContext,
) -> str:
    """Remove all completed tasks from the task list."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    if conversation.task_list is None or len(conversation.task_list) == 0:
        return "Task list is empty."

    task_list = conversation.task_list
    completed_count = sum(1 for item in task_list if item.is_complete)

    if completed_count == 0:
        return "No completed tasks to remove."

    task_list.clear_complete_items()

    logger.debug(f"Cleared {completed_count} completed tasks from task list")

    return f"Removed {completed_count} completed task(s).\n\nNote: Changes will be visible in the task list after the next summarization."
