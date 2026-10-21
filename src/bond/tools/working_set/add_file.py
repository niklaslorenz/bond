import logging

from bond.conversation.working_set import WorkingSet
from bond.conversation.working_set_item import FileReferenceItem
from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="add_working_set_file",
    description="Add a file reference to the working set. Use this to keep important files in context. You can optionally specify a line range. Changes become visible after summarization.",
    parameters={
        "path": tool.FunctionParameter(
            type="string",
            description="The path to the file (absolute or relative to current working directory)",
        ),
        "start_line": tool.FunctionParameter(
            type="integer",
            description="The first line to include (0-based). Optional.",
        ),
        "end_line": tool.FunctionParameter(
            type="integer",
            description="The last line to include (0-based, exclusive). Optional.",
        ),
    },
    required=["path"],
)
def add_working_set_file(
    context: ToolCallContext,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Add a file reference to the working set."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    # Initialize working set if it doesn't exist
    if conversation.working_set is None:
        conversation.working_set = WorkingSet()

    item = FileReferenceItem(
        path=path,
        start_line=start_line,
        end_line=end_line,
    )
    conversation.working_set.add_item(item)

    logger.debug(f"Added file reference to working set: {path}")

    result = f"Added file reference to working set: {path}"
    if start_line is not None or end_line is not None:
        result += f" (lines {start_line or 0}-{end_line or 'eof'})"
    result += "\n\nNote: Changes will be visible in the working set after the next summarization."
    return result
