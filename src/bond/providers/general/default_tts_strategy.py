from typing import Any

from returns.result import Failure, Result, Success

from bond.endpoints.tts import TTSEndpoint, TTSResponse


class DefaultTTSStrategy:
    def __init__(
        self,
        endpoint: TTSEndpoint,
        model: str,
        voice: str,
        options: dict[str, Any] | None = None,
        max_retries: int = 3,
    ):
        self._endpoint = endpoint
        self._model = model
        self._voice = voice
        self._options = options or {}
        self._max_retries = max_retries

    def __call__(self, content: str) -> Result[TTSResponse, str]:
        try:
            return Success(
                self._endpoint.tts(
                    self._model, self._voice, content, self._options, self._max_retries
                )
            )
        except Exception as e:
            return Failure(f"An error occured while generating voice: ({type(e)}): {e}")
        pass
