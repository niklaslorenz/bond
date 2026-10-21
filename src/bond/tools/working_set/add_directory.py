import logging

from bond.conversation.working_set import WorkingSet
from bond.conversation.working_set_item import DirectoryReferenceItem
from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="add_working_set_directory",
    description="Add a directory listing to the working set. Use this to keep directory structures in context. Changes become visible after summarization.",
    parameters={
        "path": tool.FunctionParameter(
            type="string",
            description="The path to the directory (absolute or relative to current working directory)",
        ),
        "pattern": tool.FunctionParameter(
            type="string",
            description="Glob pattern to match files (e.g., '*.py', '**/*.txt')",
        ),
        "recursive": tool.FunctionParameter(
            type="boolean",
            description="Whether to search recursively. Default is false.",
        ),
        "case_sensitive": tool.FunctionParameter(
            type="boolean",
            description="Whether the pattern match is case sensitive. Default is true.",
        ),
    },
    required=["path", "pattern"],
)
def add_working_set_directory(
    context: ToolCallContext,
    path: str,
    pattern: str,
    recursive: bool = False,
    case_sensitive: bool = True,
) -> str:
    """Add a directory reference to the working set."""
    conversation = context.conversation
    if conversation is None:
        return "Error: No conversation context available."

    # Initialize working set if it doesn't exist
    if conversation.working_set is None:
        conversation.working_set = WorkingSet()

    item = DirectoryReferenceItem(
        path=path,
        pattern=pattern,
        recursive=recursive,
        case_sensitive=case_sensitive,
    )
    conversation.working_set.add_item(item)

    logger.debug(f"Added directory reference to working set: {path} (pattern: {pattern})")

    result = f"Added directory reference to working set: {path}"
    result += f"\n  Pattern: {pattern}"
    result += f"\n  Recursive: {recursive}"
    result += f"\n  Case sensitive: {case_sensitive}"
    result += "\n\nNote: Changes will be visible in the working set after the next summarization."
    return result
