import logging

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="complete_tasks",
    description="Mark one or more tasks as complete by their index (0-based). Use this when you have finished working on a task. Changes become visible after summarization.",
    parameters={
        "indices": tool.FunctionParameter(
            type="array",
            description="List of task indices (0-based) to mark as complete",
        ),
    },
    required=["indices"],
)
def complete_tasks(
    context: ToolCallContext,
    indices: list[int],
) -> str:
    """Mark one or more tasks as complete."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    if conversation.task_list is None or len(conversation.task_list) == 0:
        return "Error: Task list is empty."

    task_list = conversation.task_list
    completed = []
    errors = []

    for idx in indices:
        if idx < 0 or idx >= len(task_list):
            errors.append(f"Index {idx} is out of range (0-{len(task_list) - 1})")
            continue
        item = task_list.complete_item(idx)
        completed.append(f"  - [{item.index}] {item.description}")

    result_parts = []
    if completed:
        result_parts.append(f"Marked {len(completed)} task(s) as complete:\n" + "\n".join(completed))
    if errors:
        result_parts.append("Errors:\n" + "\n".join(errors))

    result_parts.append("\nNote: Changes will be visible in the task list after the next summarization.")
    return "\n".join(result_parts)
