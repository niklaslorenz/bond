import logging

from bond.conversation.task_list import TaskList
from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="add_tasks",
    description="Add one or more tasks to the task list. Use this to track work that needs to be done. Changes become visible after summarization.",
    parameters={
        "tasks": tool.FunctionParameter(
            type="array",
            description="List of task descriptions to add",
        ),
    },
    required=["tasks"],
)
def add_tasks(
    context: ToolCallContext,
    tasks: list[str],
) -> str:
    """Add one or more tasks to the task list."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    # Initialize task list if it doesn't exist
    if conversation.task_list is None:
        conversation.task_list = TaskList()

    # Add each task
    added = []
    for task_desc in tasks:
        item = conversation.task_list.add_item(task_desc)
        added.append(f"  - {task_desc}")

    logger.debug(f"Added {len(added)} tasks to task list")

    result = f"Added {len(added)} task(s):\n" + "\n".join(added)
    result += "\n\nNote: Changes will be visible in the task list after the next summarization."
    return result