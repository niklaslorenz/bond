from pydantic import BaseModel
from returns.result import Failure, Result, Success

from bond.endpoints.tts import TTSEndpoint, TTSResponse


class DefaultTTSOptions(BaseModel):
    model: str
    voice: str


class DefaultTTSCapability:
    def __init__(
        self,
        options: DefaultTTSOptions,
        endpoint: TTSEndpoint,
        max_retries: int = 3,
    ):
        self._options = options
        self._endpoint = endpoint
        self._max_retries = max_retries

    def __call__(self, content: str) -> Result[TTSResponse, str]:
        try:
            return Success(
                self._endpoint.tts(
                    self._options.model,
                    self._options.voice,
                    content,
                    {},
                    self._max_retries,
                )
            )
        except Exception as e:
            return Failure(f"An error occured while generating voice: ({type(e)}): {e}")
