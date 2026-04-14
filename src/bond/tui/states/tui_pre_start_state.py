import logging

from bond.behaviours import behaviour_event
from bond.tui.states.tui_state import TuiState, tui_event

logger = logging.getLogger(__name__)


class TuiPreStartState(TuiState):

    def handle_start_event(self, _: tui_event.StartEvent):
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

    def handle_waiting_for_input_behaviour_event(
        self, _: behaviour_event.WaitingForInputEvent
    ):
        from . import TuiIdleState

        self.machine.change_state(TuiIdleState(self.machine))
