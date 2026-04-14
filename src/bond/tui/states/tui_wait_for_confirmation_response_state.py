from concurrent.futures import Future
from dataclasses import dataclass

from bond.tui.event import RequestConfirmEvent
from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState


@dataclass
class TuiWaitForConfirmationResponseState(TuiState):
    previous_state: TuiState
    request: str
    result: Future[bool]

    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Waiting")
        self.machine.get_app().open_confirmation_prompt(self.request)

    def handle_request_confirm_event(self, event: RequestConfirmEvent):
        self.result.set_result(event.accepted)
        self.machine.change_state(self.previous_state)
