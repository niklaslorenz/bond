import email.utils
import logging
from datetime import datetime, timezone
from time import sleep
from typing import Callable

import requests

_retry_codes: list[int] = [408, 429, 500, 502, 503, 504]

http_logger = logging.getLogger(__name__ + ".http")


def http_retry_loop(
    callback: Callable[[], requests.Response], max_retries: int
) -> requests.Response:
    response: requests.Response
    for i in range(max_retries + 1):
        response = callback()
        if response.status_code == 200:
            return response
        if response.status_code in _retry_codes:
            if i < max_retries:
                retry_after = response.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        retry_after = int(retry_after)
                    except ValueError:
                        dt = email.utils.parsedate_to_datetime(retry_after)
                        now = datetime.now(dt.tzinfo or timezone.utc)
                        retry_after = (dt - now).total_seconds()
                else:
                    retry_after = 2**i
                retry_after = max(1, retry_after)
                http_logger.warning(
                    f"http error {response.status_code}, retrying after {retry_after} seconds ({i+1}/{max_retries})"
                )
                http_logger.debug(f"http error message: {response.text}")
                sleep(retry_after)
        else:
            http_logger.error(f"http error {response.status_code}:\n{response.text}")
            response.raise_for_status()
            raise RuntimeError("Unreachable")
    http_logger.error(
        f"http error {response.status_code} (max retries exceeded):\n{response.text}"
    )
    response.raise_for_status()
    raise RuntimeError("Unreachable")
