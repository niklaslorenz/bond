from dataclasses import dataclass

from bond.tui.states.tui_state import TuiState


@dataclass
class TuiStartState(TuiState):
    persona_name: str

    def on_exit(self, destination: TuiState):
        self.machine.get_app().set_persona(self.persona_name)
