from concurrent.futures import Future
from dataclasses import dataclass

from bond.behaviours.behaviour_event import (CancelRequestConfirmationEvent,
                                             ShowConversationSelectorEvent)
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

    def handle_cancel_request_confirmation_behaviour_event(
        self, _: CancelRequestConfirmationEvent
    ):
        self.machine.notify("Cancelling confirmation request")
        self.machine.get_app().close_popup()
        self.machine.change_state(self.previous_state)

    def handle_show_conversation_selector_behaviour_event(
        self, event: ShowConversationSelectorEvent
    ):
        self.handle_invalid_behaviour_event(event)
