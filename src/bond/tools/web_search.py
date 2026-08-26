import logging

import ddgs

from bond.tools import tool

logger = logging.getLogger(__name__)


def _try_get(cont, name) -> str | None:
    val = cont.get(name)
    if val is None:
        logger.warning(f"Could not retrieve {name} from search result")
    return val


@tool.tool(
    name="search_the_web",
    description="""
    Perform a web search using DuckDuckGo and return structured results.
    """,
    parameters={
        "query": tool.FunctionParameter(
            type="string", description="The search query string"
        ),
        "max_results": tool.FunctionParameter(
            type="integer",
            description="Maximum number of results to return (default: 5)",
        ),
    },
    required=["query"],
)
def search_the_web(
    _: tool.ToolCallContext, query: str, max_results: int = 5
) -> list[dict[str, str]]:
    try:
        results = ddgs.DDGS().text(query, backend="auto", max_results=max_results)
        return [
            {
                "title": _try_get(r, "title") or "[Could not retrieve title]",
                "link": _try_get(r, "href") or "[Could not retrive link]",
                "snippet": _try_get(r, "body") or "[No description available]",
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error during web search: {type(e).__name__}: {e}")
        return []
