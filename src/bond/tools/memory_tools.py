import json
import logging
from typing import Any

from bond.tools import tool
from bond.tools.tool import ToolCallContext

logger = logging.getLogger(__name__)


@tool.tool(
    name="store_memory",
    description="Store information in the vector store memory.",
    parameters={
        "content": tool.FunctionParameter(
            type="string",
            description="The information to store in memory",
        ),
    },
    required=["content"],
)
def store_memory(
    context: ToolCallContext,
    content: str,
) -> str:
    """
    Store information in the vector store memory.
    """
    logger.debug(f"Store memory tool called with content: {content}")

    # Get persona from context
    persona = context.persona
    if persona is None:
        err_msg = "Persona is not set in the tool call context"
        logger.error(err_msg)
        return json.dumps(
            {
                "status": "error",
                "error": "Backend misconfigured. Tool call context is missing the persona",
            }
        )

    # Get memory capability from persona
    memory = persona.memory

    if memory is None:
        logger.error(f"Persona '{persona.name}' has no memory capability")
        return json.dumps(
            {
                "status": "error",
                "error": "No memory capability available",
            }
        )

    try:
        memory.store(content)
        return json.dumps(
            {
                "status": "success",
                "operation": "store",
                "content": content,
                "message": "Information stored in memory",
            }
        )
    except Exception as e:
        logger.error(f"Memory store operation failed: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "content": content,
            }
        )


@tool.tool(
    name="recall_memory",
    description="Recall information from the vector store memory.",
    parameters={
        "query": tool.FunctionParameter(
            type="string",
            description="The query to search for in memory",
        ),
        "k": tool.FunctionParameter(
            type="integer",
            description="The number of elements to retrieve (default: 3)",
        ),
    },
    required=["query"],
)
def recall_memory(
    context: ToolCallContext,
    query: str,
    k: int = 3,
) -> str:
    """
    Recall information from the vector store memory.
    """
    logger.info(f"Recall memory tool called with query: {query}, k: {k}")

    # Get persona from context
    persona = context.persona
    if persona is None:
        err_msg = "Persona is not set in the tool call context"
        logger.error(err_msg)
        return json.dumps(
            {
                "status": "error",
                "error": "Backend misconfigured. Tool call context is missing the persona",
            }
        )

    # Get memory capability from persona
    memory = persona.memory

    if memory is None:
        logger.error(f"Persona '{persona.name}' has no memory capability")
        return json.dumps(
            {
                "status": "error",
                "error": "No memory capability available",
            }
        )

    try:
        result = memory.direct_query(query, k=k)
        return json.dumps(
            {
                "status": "success",
                "operation": "query",
                "k": k,
                "result": [element.model_dump() for element in result],
            }
        )
    except Exception as e:
        logger.error(f"Memory query operation failed: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "k": k,
            }
        )
