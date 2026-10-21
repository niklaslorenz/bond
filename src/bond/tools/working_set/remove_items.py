import logging

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="remove_working_set_items",
    description="Remove one or more items from the working set by their index (0-based). Use this to remove items that are no longer relevant. Changes become visible after summarization.",
    parameters={
        "indices": tool.FunctionParameter(
            type="array",
            description="List of item indices (0-based) to remove",
        ),
    },
    required=["indices"],
)
def remove_working_set_items(
    context: ToolCallContext,
    indices: list[int],
) -> str:
    """Remove one or more items from the working set."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    if conversation.working_set is None or len(conversation.working_set) == 0:
        return "Error: Working set is empty."

    working_set = conversation.working_set
    removed = []
    errors = []

    # Sort indices in descending order to remove from end to start
    # This prevents index shifting issues
    for idx in sorted(indices, reverse=True):
        if idx < 0 or idx >= len(working_set):
            errors.append(f"Index {idx} is out of range (0-{len(working_set) - 1})")
            continue
        item = working_set.remove_item(idx)
        # Describe what was removed
        if hasattr(item, 'type'):
            if item.type == "text":
                preview = item.text[:50] + "..." if len(item.text) > 50 else item.text
                removed.append(f"  - [text] {preview}")
            elif item.type == "file":
                removed.append(f"  - [file] {item.path}")
            elif item.type == "directory":
                removed.append(f"  - [directory] {item.path} ({item.pattern})")
        else:
            removed.append(f"  - [unknown item type]")

    result_parts = []
    if removed:
        result_parts.append(f"Removed {len(removed)} item(s) from working set:\n" + "\n".join(reversed(removed)))
    if errors:
        result_parts.append("Errors:\n" + "\n".join(errors))

    result_parts.append("\nNote: Changes will be visible in the working set after the next summarization.")
    return "\n".join(result_parts)
