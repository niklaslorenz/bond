import tempfile
from typing import Any, Protocol

from playsound3 import playsound
from pydantic import BaseModel


class TTSResponse(BaseModel):
    wav_audio: bytes

    def play(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            f.write(self.wav_audio)
            f.flush()
            playsound(f.name)
        return


class TTSEndpoint(Protocol):
    def tts(
        self,
        model: str,
        voice: str,
        content: str,
        options: dict[str, Any],
        max_retries: int = 3,
    ) -> TTSResponse: ...
