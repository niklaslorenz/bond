from typing import Protocol

from returns.result import Result

from bond.endpoints.tts import TTSResponse


class TTSCapability(Protocol):
    def __call__(self, content: str) -> Result[TTSResponse, str]: ...
