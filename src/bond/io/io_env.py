from dataclasses import dataclass
from typing import TextIO


@dataclass
class IOEnvironment:
    text_in: TextIO | None
    text_out: TextIO | None
    thought_out: TextIO | None

    def handle_text(self, text: str):
        if self.text_out is not None:
            self.text_out.write(text)

    def handle_thought(self, thought: str):
        if self.thought_out is not None:
            self.thought_out.write(thought)
