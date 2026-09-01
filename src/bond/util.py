import email.utils
import logging
import os
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
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


def resolve_api_key(api_key_raw: str) -> str:
    if api_key_raw.startswith("ENV:"):
        api_key = os.getenv(api_key_raw[4:])
        if api_key is None:
            raise RuntimeError(
                f"Could not read api key from environment variable {api_key_raw[4:]}"
            )
        return api_key
    return api_key_raw


def parse_sse_stream(stream):
    """
    Parses an SSE stream (iterator of bytes or lines) into events.
    Yields each event's data as a string.
    """
    event_buffer = []
    for line in stream:
        if not line.strip():
            # Empty line: end of event
            if event_buffer:
                event_data = b"\n".join(event_buffer).decode("utf-8")
                # Remove 'data:' prefix and strip
                if event_data.startswith("data:"):
                    yield event_data[5:].strip()
                event_buffer = []
        else:
            event_buffer.append(line)
    # Handle any remaining data after stream ends
    if event_buffer:
        event_data = b"\n".join(event_buffer).decode("utf-8")
        if event_data.startswith("data:"):
            yield event_data[5:].strip()


def setup_logger(debug: bool, log_file_name: str):
    logger = logging.getLogger("bond")
    log_dir = Path("~/.local/share/bond/logs/").expanduser().absolute()
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.handlers.clear()
    handler = TimedRotatingFileHandler(
        filename=(log_dir / log_file_name).as_posix(),
        when="midnight",
        interval=1,
        backupCount=10,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
