from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.tui.states.tui_state import TuiState


@dataclass
class TuiWaitForStopState(TuiState):
    def handle_stop_behaviour_event(self, event: behaviour_event.StopEvent):
        from . import TuiStopState

        self.machine.change_state(TuiStopState(self.machine))
