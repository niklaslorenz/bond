from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from bond.behaviours.types import LoopStatus


class StatusBar(Static):
    persona = reactive("<unknown>")
    status = reactive("Idle")
    context_length = reactive(0)
    cache_rate = reactive(None)

    def __init__(
        self,
        persona: str = "<unknown>",
        status: str = "<unknown>",
        context_length: int = 0,
    ):
        super().__init__(id="status-bar")
        self.persona = persona
        self.status = status
        self.context_length = context_length

    def render(self) -> Text:
        return Text.assemble(
            ("Persona: ", "bold"),
            f"{self.persona}  ",
            ("Status: ", "bold"),
            f"{self.status}  ",
            ("Context: ", "bold"),
            f"{self.context_length}  ",
            ("Cache Rate: ", "bold"),
            f"{int(self.cache_rate * 100)}%" if self.cache_rate is not None else "?",
        )

    # Control

    def set_status(self, status: LoopStatus):
        self.status = status

    def set_usage(self, usage: int):
        self.context_length = usage

    def set_cache_rate(self, cache_rate: float | None):
        self.cache_rate = cache_rate

    def set_persona(self, persona_name: str):
        self.persona = persona_name
