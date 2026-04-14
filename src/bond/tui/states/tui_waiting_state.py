from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState


@dataclass
class TuiWaitingState(TuiState):
    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Waiting")

    def handle_response_start_behaviour_event(
        self, event: behaviour_event.ResponseStartEvent
    ):
        msg = self.machine.get_app().add_assistant_message(
            event.author, None, None, True
        )
        from . import TuiReceivingState

        self.machine.change_state(TuiReceivingState(self.machine, msg))

    def handle_waiting_for_input_behaviour_event(
        self, event: behaviour_event.WaitingForInputEvent
    ):
        from . import TuiIdleState

        self.machine.change_state(TuiIdleState(self.machine))

    def handle_call_tool_behaviour_event(self, event: behaviour_event.CallToolEvent):
        block = self.machine.get_app().add_tool_call(event.call.function.name, True)
        from . import TuiWaitForToolResultState

        self.machine.change_state(TuiWaitForToolResultState(self.machine, block))

    def handle_change_persona_behaviour_event(
        self, event: behaviour_event.ChangePersonaEvent
    ):
        self.machine.get_app().set_persona(event.name, event.provider)

    def handle_clear_chat_behaviour_event(self, event: behaviour_event.ClearChatEvent):
        self.machine.get_app().clear_chat()

    def handle_restore_conversation_behaviour_event(
        self, event: behaviour_event.RestoreConversationEvent
    ):
        self.machine.get_app().synchronize(event.conversation)
