from dataclasses import dataclass

from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState


@dataclass
class TuiWaitForCommandResponseState(TuiState):
    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Waiting")
