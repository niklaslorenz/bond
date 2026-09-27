import io
import wave
from typing import Any, Protocol

import simpleaudio as sa
from pydantic import BaseModel


class TTSResponse(BaseModel):
    wav_audio: bytes

    def play(self):
        with wave.open(io.BytesIO(self.wav_audio), "rb") as wav:
            audio = wav.readframes(wav.getnframes())
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()

        play = sa.play_buffer(
            audio,
            channels,
            sample_width,
            sample_rate,
        )

        play.wait_done()

        # Keep the object around until after playback
        print("finished")


class TTSEndpoint(Protocol):
    def tts(
        self, model: str, content: str, options: dict[str, Any], max_retries: int = 3
    ): ...
