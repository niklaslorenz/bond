import logging

from bond.conversation.working_set import WorkingSet
from bond.conversation.working_set_item import TextItem
from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="add_working_set_text",
    description="Add a text snippet to the working set. Use this to add notes, code snippets, or any text content you want to keep in context. Changes become visible after summarization.",
    parameters={
        "text": tool.FunctionParameter(
            type="string",
            description="The text content to add to the working set",
        ),
    },
    required=["text"],
)
def add_working_set_text(
    context: ToolCallContext,
    text: str,
) -> str:
    """Add a text item to the working set."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    # Initialize working set if it doesn't exist
    if conversation.working_set is None:
        conversation.working_set = WorkingSet()

    item = TextItem(text=text)
    conversation.working_set.add_item(item)

    logger.debug(f"Added text item to working set ({len(text)} chars)")

    result = "Added text item to working set:\n"
    result += f"  ---\n  {text}\n  ---"
    result += "\n\nNote: Changes will be visible in the working set after the next summarization."
    return result
