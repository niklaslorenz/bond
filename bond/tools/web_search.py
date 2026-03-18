import logging

import ddgs

logger = logging.getLogger(__name__)


def _try_get(cont, name) -> str | None:
    val = cont.get(name)
    if val is None:
        logger.warning(f"Could not retrieve {name} from search result")
    return val


def search_the_web(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Perform a web search using DuckDuckGo and return structured results.

    Args:
        query (str): The search query string.
        max_results (int): Maximum number of results to return (default: 5).

    Returns:
        list[dict[str, str]]: A list of result dictionaries. Each result contains:
            - "title" (str): The result title.
            - "link" (str): The result URL.
            - "snippet" (str): A short description or snippet for the result.
              If no description is available, the value will be "No description available."
    """
    try:
        results = ddgs.DDGS().text(query, backend="duckduckgo", max_results=max_results)
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
