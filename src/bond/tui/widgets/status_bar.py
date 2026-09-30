from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from bond.tui.types import TuiStatus


class StatusBar(Static):
    persona = reactive("<unknown>")
    status = reactive("Idle")
    context_length = reactive(0)

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
            f"{self.context_length}",
        )

    # Control

    def set_status(self, status: TuiStatus):
        self.status = status

    def set_usage(self, usage: int):
        self.context_length = usage

    def set_persona(self, persona_name: str):
        self.persona = persona_name
