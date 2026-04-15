from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState
from bond.behaviours.behaviour_event import ShowConversationSelectorEvent


@dataclass
class TuiWaitForCommandResponseState(TuiState):
    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Waiting")

    def handle_command_response_behaviour_event(
        self, _: behaviour_event.CommandResponseEvent
    ):
        from . import TuiIdleState

        self.machine.change_state(TuiIdleState(self.machine))

    def handle_change_persona_behaviour_event(
        self, event: behaviour_event.ChangePersonaEvent
    ):
        self.machine.get_app().set_persona(event.name, event.provider)

    def handle_restore_conversation_behaviour_event(
        self, event: behaviour_event.RestoreConversationEvent
    ):
        self.machine.get_app().synchronize(event.conversation)

    def handle_show_conversation_selector_behaviour_event(
        self, event: ShowConversationSelectorEvent
    ):
        from . import TuiConversationSelectorState

        self.machine.change_state(
            TuiConversationSelectorState(self.machine, event.conversations)
        )
