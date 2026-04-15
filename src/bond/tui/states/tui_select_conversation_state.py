import logging
from dataclasses import dataclass
from shlex import quote

from bond.behaviours import behaviour_event
from bond.behaviours.behaviour_signal import CommandSignal
from bond.tui.event import ConversationSelectedEvent
from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState

logger = logging.getLogger(__name__)


@dataclass
class TuiConversationSelectorState(TuiState):
    conversations: list[str]

    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Waiting")
        self.machine.get_app().open_conversation_selector(self.conversations)

    def on_exit(self, destination: ITuiState):
        self.machine.get_app().close_popup()

    def handle_conversation_selected_event(self, event: ConversationSelectedEvent):
        self.machine.get_app().close_popup()
        if event.name is not None:
            self.machine.send_signal(CommandSignal(command=f"load {quote(event.name)}"))
            from . import TuiWaitForCommandResponseState

            self.machine.change_state(TuiWaitForCommandResponseState(self.machine))
        else:
            from . import TuiIdleState

            self.machine.change_state(TuiIdleState(self.machine))

    def handle_command_response_behaviour_event(
        self, _: behaviour_event.CommandResponseEvent
    ):
        pass

    def handle_request_confirmation_behaviour_event(
        self, event: behaviour_event.RequestConfirmationEvent
    ):
        self.handle_invalid_behaviour_event(event)

    def handle_waiting_for_input_behaviour_event(
        self, _: behaviour_event.WaitingForInputEvent
    ):
        pass
