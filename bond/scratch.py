import logging
import sys

from bond.behaviours.single_turn import SingleTurn
from bond.providers.mistral import Mistral
from bond.tools.tool import Toolbox
from bond.tools.web_access import access_web
from bond.tools.web_search import search_the_web

logger = logging.getLogger("bond")

tools = [
    (
        {
            "type": "function",
            "function": {
                "name": "search_the_web",
                "description": "searches the web based on the provided query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query to search for",
                        }
                    },
                },
            },
        },
        search_the_web,
    )
]

mistral = Mistral()
toolbox = Toolbox([search_the_web, access_web])
turn = SingleTurn(mistral.api, "mistral-small-latest", toolbox)


logging.basicConfig(
    stream=sys.stdout,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger.setLevel(logging.DEBUG)
