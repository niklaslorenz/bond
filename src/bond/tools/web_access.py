import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from returns.result import Failure, Result, Success

from bond.tools import tool

from . import logger


class WebScraper:
    def __init__(self, agent_name: str):
        self.user_agent = agent_name
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def can_fetch(self, url: str) -> tuple[bool, int]:
        """Check if scraping is allowed by robots.txt for the given URL."""
        rp = RobotFileParser()
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            rp.set_url(robots_url)
            rp.read()
            crawl_delay_raw = rp.crawl_delay(self.user_agent)
            crawl_delay: int
            try:
                crawl_delay = int(crawl_delay_raw) if crawl_delay_raw is not None else 1
            except ValueError:
                logger.debug(
                    f"Could not parse crawl_delay: '{crawl_delay_raw}'. Assuming 1 second"
                )
                crawl_delay = 1
            return rp.can_fetch(self.user_agent, url), crawl_delay
        except Exception:
            logger.debug(f"Could not find robots.txt for '{url}'")
            return True, 1  # Assume allowed if robots.txt is unreachable

    def scrape(self, url, max_retries: int = 3, delay: int = 2) -> Result[str, str]:
        """Fetch and parse the main content of a webpage."""
        max_retries = max(0, max_retries)
        for attempt in range(max_retries + 1):
            try:
                allowed, crawl_delay = self.can_fetch(url)
                if not allowed:
                    return Failure(f"Scraping blocked by robots.txt for {url}")

                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Get text and clean whitespace
                text = soup.get_text(separator=" ", strip=True)
                return Success(text)

            except requests.RequestException as e:
                logger.debug(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == max_retries - 1:
                    return Failure(f"Request failed: {e}")
            time.sleep(max(5, crawl_delay, delay))  # Wait before retrying
        raise RuntimeError("unreachable")


@tool.tool(
    name="access_web",
    description="""
    Access a website's readable content. If a website does not allow
    scraping with automated tools, then an error description is returned.
    """,
    parameters={
        "url": tool.FunctionParameter(
            type="string", description="The website's full url"
        )
    },
    required=["url"],
)
def access_web(context: tool.ToolCallContext, url: str) -> str:
    scraper = WebScraper("Bond-WebAgent")
    result: Result[str, str] = scraper.scrape(url)
    if isinstance(result, Success):
        return result.unwrap()
    else:
        return result.failure()
