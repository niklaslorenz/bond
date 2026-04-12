from dataclasses import dataclass

from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState


@dataclass
class TuiStopState(TuiState):
    def on_enter(self, source: ITuiState):
        self.machine.stop()
