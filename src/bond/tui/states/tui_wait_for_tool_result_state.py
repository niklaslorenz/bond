from dataclasses import dataclass

from bond.behaviours import behaviour_event
from bond.tui.states.tui_state import TuiState
from bond.tui.types import ITuiState, ITuiStateMachine
from bond.tui.widgets import ToolResultBlock


@dataclass
class TuiWaitForToolResultState(TuiState):
    block: ToolResultBlock

    def __init__(self, machine: ITuiStateMachine, block: ToolResultBlock):
        super().__init__(machine)
        self.block = block

    def on_enter(self, source: ITuiState):
        self.machine.get_app().set_status("Tool Call")

    def handle_tool_return_behaviour_event(
        self, event: behaviour_event.ToolReturnEvent
    ):
        self.block.append(event.result)
        from . import TuiWaitingState

        self.machine.change_state(TuiWaitingState(self.machine))

    def handle_request_confirmation_behaviour_event(
        self, event: behaviour_event.RequestConfirmationEvent
    ):
        from . import TuiWaitForConfirmationResponseState

        self.machine.change_state(
            TuiWaitForConfirmationResponseState(
                self.machine, self, event.request, event.result()
            )
        )
