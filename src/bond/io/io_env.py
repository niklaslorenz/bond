from dataclasses import dataclass
from typing import TextIO


@dataclass
class IOEnvironment:
    text_in: TextIO | None
    text_out: TextIO | None
    thought_out: TextIO | None
