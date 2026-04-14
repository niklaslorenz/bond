from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState


@dataclass
class TuiWaitForStopState(TuiState):

    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Waiting")

    def handle_stop_behaviour_event(self, event: behaviour_event.StopEvent):
        from . import TuiStopState

        self.machine.change_state(TuiStopState(self.machine))
