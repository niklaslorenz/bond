import logging

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="delete_tasks",
    description="Delete one or more tasks from the task list by their index (0-based). Use this to remove tasks that are no longer relevant. Changes become visible after summarization.",
    parameters={
        "indices": tool.FunctionParameter(
            type="array",
            description="List of task indices (0-based) to delete",
        ),
    },
    required=["indices"],
)
def delete_tasks(
    context: ToolCallContext,
    indices: list[int],
) -> str:
    """Delete one or more tasks from the task list."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    if conversation.task_list is None or len(conversation.task_list) == 0:
        return "Error: Task list is empty."

    task_list = conversation.task_list
    deleted = []
    errors = []

    # Sort indices in descending order to delete from end to start
    # This prevents index shifting issues
    for idx in sorted(indices, reverse=True):
        if idx < 0 or idx >= len(task_list):
            errors.append(f"Index {idx} is out of range (0-{len(task_list) - 1})")
            continue
        item = task_list.remove_item(idx)
        deleted.append(f"  - [{item.index}] {item.description}")

    result_parts = []
    if deleted:
        result_parts.append(f"Deleted {len(deleted)} task(s):\n" + "\n".join(reversed(deleted)))
    if errors:
        result_parts.append("Errors:\n" + "\n".join(errors))

    result_parts.append("\nNote: Changes will be visible in the task list after the next summarization.")
    return "\n".join(result_parts)
